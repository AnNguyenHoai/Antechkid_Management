"""Bounded, best-effort background mirror for COMMITTED RV-02 outbox records.

Invariant: this worker NEVER opens SQLCipher, touches a SQLAlchemy Session,
publishes Git refs, or changes authoritative state. A crash/queue overflow may
leave an INCOMPLETE external mirror; the committed SQLCipher outbox and existing
WAL-consistent recovery capture remain the durable provenance source.

Use drain_before_capture() after WRITE has been quiesced but before the
existing WriteRecoveryJournal.preserve('before-publish') operation.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

_MAX_PENDING = 512


class _MirrorWorker:
    def __init__(self, max_pending: int = _MAX_PENDING):
        self._jobs: queue.Queue[tuple[Path, bytes, tuple[str, str]]] = queue.Queue(maxsize=max_pending)
        self._condition = threading.Condition()
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        # Each WRITE session has independent accounting. A failed old session
        # must never poison a new session's mirror drain result.
        self._session_counters = defaultdict(lambda: {"submitted": 0, "completed": 0, "failed": 0})
        self._worker: threading.Thread | None = None

    def enqueue(self, root: Path, committed_payload: bytes, *, session_id: str | None = None) -> bool:
        """Never wait for disk/crypto from caller's Save/UI thread."""
        # Prevent unbounded memory/disk queue growth. A refused event is still
        # committed in SQLCipher and must be treated as mirror INCOMPLETE.
        scope = (str(Path(root).resolve()), session_id or "__unscoped__")
        with self._condition:
            try:
                self._jobs.put_nowait((Path(root), bytes(committed_payload), scope))
            except queue.Full:
                self._failed += 1
                self._session_counters[scope]["failed"] += 1
                logger.error(
                    "RV-02 mirror backlog full; committed SQLCipher outbox is intact. "
                    "Recovery mirror is INCOMPLETE until captured and reconciled."
                )
                self._condition.notify_all()
                return False
            self._submitted += 1
            self._session_counters[scope]["submitted"] += 1
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._run,
                    name="rv02-encrypted-mirror",
                    daemon=True,
                )
                self._worker.start()
            self._condition.notify_all()
            return True

    def _run(self) -> None:
        from centermanager.database.encryption import DatabaseKeyStore
        from centermanager.platform.recovery_change_mirror import mirror_committed_payload

        while True:
            root, payload, scope = self._jobs.get()
            try:
                # Key loading, AES-GCM, file creation, fsync and anti-virus I/O
                # stay off the Save/UI path. Do not retain SQLCipher handles.
                key = DatabaseKeyStore().load()
                mirror_committed_payload(payload, recovery_root=root, encryption_key=key)
            except Exception:
                logger.exception(
                    "RV-02 background mirror failed; an authenticated SQLCipher "
                    "recovery capture remains required (mirror INCOMPLETE)"
                )
                with self._condition:
                    self._failed += 1
                    self._session_counters[scope]["failed"] += 1
            finally:
                with self._condition:
                    self._completed += 1
                    self._session_counters[scope]["completed"] += 1
                    self._condition.notify_all()
                self._jobs.task_done()

    def drain(
        self,
        timeout_seconds: float = 5.0,
        *,
        recovery_root: Path | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Wait at most timeout for all jobs submitted before this barrier.

        Call this ONLY in the Finish Editing path after local Save has been
        quiesced and prior to the WAL-complete recovery capture. A false result
        must not be hidden or treated as an all-complete mirror.
        """
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        scope = None
        if recovery_root is not None and session_id is not None:
            scope = (str(Path(recovery_root).resolve()), session_id)
        with self._condition:
            target = (self._submitted if scope is None
                      else self._session_counters[scope]["submitted"])
            while True:
                completed = (self._completed if scope is None
                             else self._session_counters[scope]["completed"])
                if completed >= target:
                    failures = (self._failed if scope is None
                                else self._session_counters[scope]["failed"])
                    return failures == 0
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(
                        "RV-02 mirror drain deadline reached (completed=%d target=%d session=%s); "
                        "continue only with existing protected SQLCipher capture",
                        completed, target, session_id or "all",
                    )
                    return False
                self._condition.wait(remaining)

    def snapshot(self) -> dict[str, int]:
        with self._condition:
            return {
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
                "queued": self._jobs.qsize(),
            }


_WORKER = _MirrorWorker()


def submit_committed_payload(
    *, recovery_root: Path, payload: bytes, session_id: str | None = None
) -> bool:
    return _WORKER.enqueue(recovery_root, payload, session_id=session_id)


def drain_before_capture(
    timeout_seconds: float = 5.0,
    *, recovery_root: Path | None = None, session_id: str | None = None
) -> bool:
    return _WORKER.drain(
        timeout_seconds, recovery_root=recovery_root, session_id=session_id
    )


def mirror_worker_stats() -> dict[str, int]:
    return _WORKER.snapshot()
