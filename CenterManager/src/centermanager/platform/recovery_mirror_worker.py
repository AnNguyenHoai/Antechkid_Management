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

logger = logging.getLogger(__name__)

_MAX_PENDING = 512


class _MirrorWorker:
    def __init__(self, max_pending: int = _MAX_PENDING):
        self._jobs: queue.Queue[tuple[Path, bytes]] = queue.Queue(maxsize=max_pending)
        self._condition = threading.Condition()
        self._submitted = 0
        self._completed = 0
        self._failed = 0
        self._worker: threading.Thread | None = None

    def enqueue(self, root: Path, committed_payload: bytes) -> bool:
        """Never wait for disk/crypto from caller's Save/UI thread."""
        # Prevent unbounded memory/disk queue growth. A refused event is still
        # committed in SQLCipher and must be treated as mirror INCOMPLETE.
        with self._condition:
            try:
                self._jobs.put_nowait((Path(root), bytes(committed_payload)))
            except queue.Full:
                self._failed += 1
                logger.error(
                    "RV-02 mirror backlog full; committed SQLCipher outbox is intact. "
                    "Recovery mirror is INCOMPLETE until captured and reconciled."
                )
                self._condition.notify_all()
                return False
            self._submitted += 1
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
            root, payload = self._jobs.get()
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
            finally:
                with self._condition:
                    self._completed += 1
                    self._condition.notify_all()
                self._jobs.task_done()

    def drain(self, timeout_seconds: float = 5.0) -> bool:
        """Wait at most timeout for all jobs submitted before this barrier.

        Call this ONLY in the Finish Editing path after local Save has been
        quiesced and prior to the WAL-complete recovery capture. A false result
        must not be hidden or treated as an all-complete mirror.
        """
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        with self._condition:
            target = self._submitted
            while self._completed < target:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(
                        "RV-02 mirror drain deadline reached (completed=%d target=%d); "
                        "continue only with existing protected SQLCipher capture",
                        self._completed, target,
                    )
                    return False
                self._condition.wait(remaining)
            return self._failed == 0

    def snapshot(self) -> dict[str, int]:
        with self._condition:
            return {
                "submitted": self._submitted,
                "completed": self._completed,
                "failed": self._failed,
                "queued": self._jobs.qsize(),
            }


_WORKER = _MirrorWorker()


def submit_committed_payload(*, recovery_root: Path, payload: bytes) -> bool:
    return _WORKER.enqueue(recovery_root, payload)


def drain_before_capture(timeout_seconds: float = 5.0) -> bool:
    return _WORKER.drain(timeout_seconds)


def mirror_worker_stats() -> dict[str, int]:
    return _WORKER.snapshot()
