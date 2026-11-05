# -*- coding: utf-8 -*-
"""WriteTransaction - Complete write transaction for Student Workspace."""
import logging
import shutil
import json
import inspect
import os
import time
import threading
from enum import Enum, auto
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.core.paths import get_paths
from centermanager.database.artifact_security import materialize_runtime_database_to_repository
from centermanager.platform.collaboration import CollaborationManager, WriteRequestResult

logger = logging.getLogger(__name__)


class WriteTransactionState(Enum):
    """State machine for write transaction."""
    IDLE = auto()
    ACQUIRING = auto()
    EDITING = auto()
    EDITING_STALE = auto()
    LOCAL_SAVED = auto()
    PUBLISHING = auto()
    PUBLISHED = auto()
    PUBLISHED_LOCK_RELEASE_PENDING = auto()
    COMPLETED = auto()
    FAILED = auto()
    OFFLINE_PENDING_PUBLISH = auto()
    WAITING = auto()
    GRANTING = auto()
    RECOVERY_REQUIRED = auto()
    # Finishing states
    FINISHING = auto()
    FINISHING_WAITING_FOR_COLLABORATION = auto()
    FINISHING_STALE = auto()
    # MAIN conflict
    PUBLISH_CONFLICT = auto()


class WriteTransactionManager:
    """
    Manages complete write transaction: Start Editing → Finish Editing.
    Implements FINISHING authority fencing, generation fencing,
    and MAIN optimistic concurrency.
    """

    def __init__(self, collaboration_manager: CollaborationManager):
        self._collab_manager = collaboration_manager
        self._state = WriteTransactionState.IDLE
        self._save_callback: Optional[Callable[[], bool]] = None
        self._on_publish_success: Optional[Callable[[], None]] = None
        self._on_publish_failure: Optional[Callable[[str], None]] = None
        self._sync_service = None
        self._version_manager = None
        self._has_changes = False
        self._dirty_student_ids: set[int] = set()
        self._pending_version: Optional[int] = None
        self._snapshot_path: Optional[Path] = None
        self._waiting_position: int = 0
        self._waiting_request_id: str = ""
        self._waiting_started_at: Optional[datetime] = None
        self._session = None
        self._last_start_error: str = ""
        self._stale_editing_reason: str = ""

        # FINISHING fields
        self._finishing_started_at: Optional[datetime] = None
        self._finishing_deadline: Optional[datetime] = None
        self._publish_intent: bool = False
        self._finishing_retry_count: int = 0

        # Generation fencing
        self._expected_generation: int = 0

        # MAIN optimistic concurrency
        self._base_main_commit: Optional[str] = None

        # Internal editing flag
        self._is_editing = False
        self._recovery_journal = None
        self._pre_handoff_clean_receipt = None
        self._generate_reports = None
        self._report_warning = ""
        self._mutation_gate = None

    def enable_local_mutation_gate(self):
        from centermanager.database.mutation_authority import gate_for
        gate_for().bind(self)

    def _open_local_mutations(self):
        if self._mutation_gate is None:
            return True
        try:
            self._mutation_gate.open()
            return True
        except Exception as exc:
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            self._is_editing = False
            self._last_start_error = f"Local mutation admission failed: {exc}. Inspect recovery before synchronization."
            return False

    @property
    def state(self) -> WriteTransactionState:
        return self._state

    @property
    def is_editing(self) -> bool:
        return self._state in (WriteTransactionState.EDITING,
                               WriteTransactionState.LOCAL_SAVED,
                               WriteTransactionState.FINISHING,
                               WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION)

    @property
    def is_waiting(self) -> bool:
        return self._state == WriteTransactionState.WAITING

    @property
    def can_edit(self) -> bool:
        return self._state in (WriteTransactionState.IDLE, WriteTransactionState.WAITING)

    @property
    def has_changes(self) -> bool:
        return self._has_changes

    @property
    def last_start_error(self) -> str:
        return self._last_start_error

    @property
    def stale_editing_reason(self) -> str:
        return self._stale_editing_reason

    def set_sync_service(self, sync_service) -> None:
        self._sync_service = sync_service

    def set_version_manager(self, version_manager) -> None:
        self._version_manager = version_manager

    def set_report_callback(self, generate) -> None:
        """Bind SQL-read-only derived report delivery after verified MAIN."""
        self._generate_reports = generate

    @property
    def report_warning(self) -> str:
        return self._report_warning

    def mark_dirty(self) -> None:
        self._has_changes = True

    def mark_student_dirty(self, student_id: int) -> None:
        self._has_changes = True
        self._dirty_student_ids.add(student_id)

    @property
    def dirty_student_ids(self) -> set[int]:
        return set(self._dirty_student_ids)

    _ALLOWED_TRANSITIONS = {
        WriteTransactionState.IDLE: {WriteTransactionState.ACQUIRING},
        WriteTransactionState.ACQUIRING: {WriteTransactionState.EDITING, WriteTransactionState.WAITING, WriteTransactionState.IDLE},
        WriteTransactionState.WAITING: {WriteTransactionState.GRANTING, WriteTransactionState.IDLE},
        WriteTransactionState.GRANTING: {WriteTransactionState.EDITING, WriteTransactionState.WAITING},
    }

    def _transition_to(self, target: WriteTransactionState, reason: str = "") -> bool:
        """Single owner for collaboration-entry state transitions.

        Existing publish/finishing substates are retained for compatibility,
        while the contention path is explicitly fenced here.
        """
        current = self._state
        if current == target:
            return True
        allowed = self._ALLOWED_TRANSITIONS.get(current)
        if allowed is not None and target not in allowed:
            logger.warning("Invalid transaction transition: %s -> %s (%s)", current.name, target.name, reason)
            return False
        self._state = target
        logger.info("Transaction transition: %s -> %s%s", current.name, target.name, f" ({reason})" if reason else "")
        return True

    def _reset_to_idle(self) -> None:
        """Reset transaction state to IDLE after completion."""
        if self._mutation_gate is not None:
            self._mutation_gate.close()
        self._state = WriteTransactionState.IDLE
        self._session = None
        self._save_callback = None
        self._on_publish_success = None
        self._on_publish_failure = None
        self._has_changes = False
        self._dirty_student_ids.clear()
        self._pending_version = None
        self._snapshot_path = None
        self._waiting_position = 0
        self._waiting_request_id = ""
        self._waiting_started_at = None
        self._finishing_started_at = None
        self._finishing_deadline = None
        self._publish_intent = False
        self._finishing_retry_count = 0
        self._expected_generation = 0
        self._base_main_commit = None
        self._is_editing = False
        self._stale_editing_reason = ""
        self._recovery_journal = None
        self._pre_handoff_clean_receipt = None
        resume_lease = getattr(self._collab_manager, "resume_write_lease_renewal", None)
        if callable(resume_lease):
            resume_lease()
        logger.info("Transaction reset to IDLE")

    # ---- Snapshot ----
    def _begin_recovery_journal(self) -> bool:
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        from centermanager.database.encryption import database_encryption_required
        journal = WriteRecoveryJournal()
        # Non-deployed, DB-less custom providers have no persistent workspace.
        # Encrypted production always requires durable metadata.
        if not database_encryption_required() and not (
            journal.database.exists() and (journal.repository / ".git").exists()
        ):
            return True
        try:
            provider = self._collab_manager._sync_provider
            token = getattr(provider, "_owned_lock_token", None)
            authority = {name: token.get(name) for name in ("session_id", "oid", "lease_revision")} if isinstance(token, dict) else {}
            receipt = self._pre_handoff_clean_receipt
            if receipt is not None:
                # The handoff layer (before it discards the previous DB)
                # already validated MAIN and sealed the migrated runtime.
                # Never reseal here: that would validate the old pre-handoff
                # receipt against a newly accepted database generation.
                journal.assert_replaceable()
                accepted = journal.inspect()
                if (accepted is None or accepted.get('status') != 'CLEAN'
                        or accepted.get('published_oid') != self._base_main_commit):
                    from centermanager.platform.write_recovery import RecoveryRequired
                    raise RecoveryRequired(
                        'WRITE handoff receipt does not match its pinned MAIN commit.'
                    )
                self._pre_handoff_clean_receipt = None
            journal.begin(self._collab_manager.get_session_id(), self._base_main_commit, authority)
            self._recovery_journal = journal
            return True
        except Exception as exc:
            self._last_start_error = f"Local recovery protection failed: {exc}. Keep the workspace; inspect recovery before retrying."
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            self._is_editing = False
            logger.error(self._last_start_error)
            return False

    def _create_snapshot(self) -> None:
        from centermanager.database.wal_safety import copy_runtime_database_for_publish
        try:
            paths = get_paths()
            if (paths.database_dir / "center.db").exists():
                snapshot_dir = paths.runtime_root / "snapshots"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                import uuid
                snapshot_path = snapshot_dir / f"pre_edit_{uuid.uuid4().hex}.db"
                copy_runtime_database_for_publish(snapshot_path)
                self._snapshot_path = snapshot_path
        except Exception:
            logger.exception("Failed to create snapshot")

    def _delete_snapshot(self) -> None:
        """Delete the transaction snapshot only after it is no longer needed."""
        snapshot_path = self._snapshot_path
        if snapshot_path is None:
            return
        try:
            if snapshot_path.exists():
                snapshot_path.unlink()
                logger.info("Snapshot deleted: %s", snapshot_path)
            self._snapshot_path = None
        except Exception:
            logger.exception("Failed to delete snapshot: %s", snapshot_path)

    def _restore_snapshot(self) -> bool:
        from centermanager.platform.write_recovery import require_replaceable
        require_replaceable()
        if self._snapshot_path and self._snapshot_path.exists():
            try:
                paths = get_paths()
                db_path = paths.database_dir / "center.db"
                shutil.copy2(self._snapshot_path, db_path)
                logger.info("Snapshot restored")
                return True
            except Exception:
                logger.exception("Failed to restore snapshot")
        return False

    def _release_grant_after_failed_consistency_check(self) -> None:
        """Release a just-acquired WRITE lease when runtime verification fails."""
        try:
            if self._collab_manager.is_writing():
                if not self._collab_manager.release_write():
                    logger.error("WRITE lease release reported failure after consistency rejection")
        except Exception:
            logger.exception("Failed to release WRITE lease after consistency rejection")

    @staticmethod
    def _explicit_method(obj, name: str):
        """Return an optional method only when the object's type declares it.

        MagicMock/dynamic proxies synthesize arbitrary attributes via getattr;
        treating those as real performance capabilities breaks compatibility
        with tests and custom providers.
        """
        if obj is None:
            return None
        declared = getattr(type(obj), name, None)
        if not callable(declared):
            return None
        method = getattr(obj, name, None)
        return method if callable(method) else None

    def _get_handoff_main_commit(self) -> Optional[str]:
        if self._sync_service is None:
            return None
        getter = self._explicit_method(
            self._sync_service,
            "get_last_write_handoff_main_commit",
        )
        if getter is None:
            return None
        try:
            return getter()
        except Exception:
            logger.debug("Unable to reuse pinned WRITE handoff MAIN commit", exc_info=True)
            return None

    def _verify_first_writer_consistency(self) -> bool:
        """Run the mandatory runtime/repository/remote barrier while WRITE is held."""
        provider = getattr(self._collab_manager, "_sync_provider", None)
        if provider is None:
            return True
        if self._sync_service is None:
            self._last_start_error = "Write consistency verification is unavailable."
            logger.error(self._last_start_error)
            return False
        try:
            if self._sync_service.execute_write_handoff_sync():
                return True
        except Exception:
            logger.exception("First-writer consistency verification raised")
        self._last_start_error = (
            "Write lock was acquired, but authoritative data consistency verification failed."
        )
        logger.error(self._last_start_error)
        return False

    def _verify_grant_before_editing(self) -> bool:
        """Fail closed if remote WRITE was revoked during DB handoff/journal prep.

        This is a new remote observation at the final mutation boundary, not
        a cached is_writing() flag or a local lock-file check. The generation
        must match the grant captured by this transaction.
        """
        provider = getattr(self._collab_manager, "_sync_provider", None)
        if provider is None:
            return True  # local-only collaboration retains existing semantics
        session = self._collab_manager.get_session()
        if session is None:
            self._last_start_error = "WRITE authority missing: no active session."
            return False
        try:
            auth = self._collab_manager.validate_write_authority(session)
            valid = bool(auth.get("valid", False))
            generation = auth.get("generation")
            if (valid and auth.get("generation_authoritative") is True
                    and generation != self._expected_generation):
                valid = False
            if valid and not self._collab_manager.is_writing():
                valid = False
            # Session equality alone is insufficient: a renewed/replaced
            # lock can have a different OID or revision. Check the provider's
            # exact locally owned token against a fresh remote observation.
            owns = getattr(type(provider), "owns_lock_observation", None)
            if valid and callable(owns):
                observed = provider.remote_lock_status()
                valid = bool(owns(
                    provider, observed, session.username, session.session_id,
                ))
            if valid:
                logger.info(
                    "Final WRITE grant validated before EDITING: generation=%s",
                    generation,
                )
                return True
            logger.error(
                "Final WRITE grant rejected before EDITING: reason=%s "
                "generation_matches=%s",
                str(auth.get("reason") or "REMOTE_AUTHORITY_NOT_VERIFIED")[:120],
                generation == self._expected_generation,
            )
        except Exception as exc:
            logger.warning(
                "Final WRITE grant observation failed before EDITING: type=%s",
                type(exc).__name__,
            )
        self._last_start_error = (
            "Remote WRITE ownership was lost or could not be verified before "
            "editing. Local changes are blocked; inspect collaboration state."
        )
        return False

    def _waiting_is_authoritative(self) -> bool:
        """A visible pending request is WAITING even in grace/ack uncertainty.

        This verifies request intent, not permission to mutate or publish.
        Only the manager's grant path may turn that intent into WRITE.
        """
        checker = self._explicit_method(self._collab_manager, "has_pending_waiting_request")
        if checker is not None:
            return checker()
        provider = getattr(self._collab_manager, "_sync_provider", None)
        if provider is None:
            return True
        try:
            remote = provider.remote_lock_status()
            return bool(remote.get("state") == "GRACE" or (
                remote.get("locked", False)
                and self._collab_manager._is_lease_valid(remote.get("lease_expires_at"))
            ))
        except Exception:
            return False

    def pause_editing_for_lost_authority(self, reason: str) -> bool:
        """Fail closed when an active editing lease can no longer be trusted."""
        if self._mutation_gate is not None and not self._mutation_gate.closed:
            self._mutation_gate.invalidate(reason or "WRITE authority is stale")
            return True
        if self._state not in (
            WriteTransactionState.EDITING,
            WriteTransactionState.LOCAL_SAVED,
        ):
            return False
        self._stale_editing_reason = (reason or "WRITE authority is stale.").strip()
        self._state = WriteTransactionState.EDITING_STALE
        self._is_editing = False
        self._collab_manager.suspend_write_lease_renewal()
        logger.warning(
            "Editing paused due to stale WRITE authority: %s",
            self._stale_editing_reason,
        )
        return True

    def pause_editing_for_idle_timeout(self) -> bool:
        """Pause a forgotten editing session without silently discarding work."""
        if self._state not in (
            WriteTransactionState.EDITING,
            WriteTransactionState.LOCAL_SAVED,
        ):
            return False
        self._stale_editing_reason = (
            "Editing was paused after prolonged inactivity. Recover editing before making more changes."
        )
        self._state = WriteTransactionState.EDITING_STALE
        self._is_editing = False
        self._collab_manager.suspend_write_lease_renewal()

        # No unpublished work: release immediately so another workstation is
        # not blocked by an abandoned editor. Dirty sessions retain the remote
        # lease until its normal expiry window, then recovery is concurrency-fenced.
        if not self._has_changes and self._collab_manager.is_writing():
            try:
                self._collab_manager.release_write()
            except Exception:
                logger.exception("Idle clean session could not release WRITE immediately")
        logger.warning(
            "Editing paused for inactivity; dirty=%s",
            self._has_changes,
        )
        return True

    def recover_stale_editing(self) -> bool:
        """Recover an EDITING_STALE / FINISHING_STALE transaction safely.

        Local work is preserved. Recovery is allowed only while remote MAIN is
        unchanged from the transaction base. A lost/expired lease may be
        reacquired without pulling the repository DB, because doing a normal
        first-writer handoff here would overwrite unpublished local work.
        """
        if self._state not in (
            WriteTransactionState.EDITING_STALE,
            WriteTransactionState.FINISHING_STALE,
        ):
            self._last_start_error = (
                f"Editing recovery is unavailable while transaction state is {self._state.name}."
            )
            return False

        provider = getattr(self._collab_manager, "_sync_provider", None)
        session = self._collab_manager.get_session()
        if session is None:
            self._last_start_error = "Editing recovery failed: no active collaboration session."
            return False

        if provider is not None:
            try:
                current_main = provider.get_remote_main_commit()
            except Exception as exc:
                self._last_start_error = f"Editing recovery could not verify MAIN: {exc}"
                logger.warning(self._last_start_error)
                return False

            if (
                self._base_main_commit is None
                or current_main is None
                or current_main != self._base_main_commit
            ):
                self._state = WriteTransactionState.PUBLISH_CONFLICT
                self._is_editing = False
                self._last_start_error = (
                    "Editing recovery stopped because authoritative MAIN changed "
                    "while this editor was stale."
                )
                logger.warning(self._last_start_error)
                return False

            try:
                remote = provider.remote_lock_status()
            except Exception as exc:
                self._last_start_error = f"Editing recovery could not read remote lock: {exc}"
                return False

            valid = bool(
                remote.get("locked", False)
                and self._collab_manager._is_lease_valid(remote.get("lease_expires_at"))
            )
            if valid and remote.get("session_id") != session.session_id:
                self._last_start_error = (
                    f"Editing recovery blocked: {remote.get('owner') or 'another editor'} "
                    "currently owns WRITE."
                )
                return False

            if valid and remote.get("session_id") == session.session_id:
                if not self._collab_manager.renew_remote_lease(force=True):
                    self._last_start_error = "Editing recovery could not renew the existing WRITE lease."
                    return False
            else:
                try:
                    self._collab_manager.clear_local_write_projection_for_recovery()
                except Exception as exc:
                    self._last_start_error = f"Editing recovery could not clear stale local state: {exc}"
                    return False

                result = self._collab_manager.request_write("recover stale editing")
                if not result.is_granted:
                    if result.is_waiting:
                        self._collab_manager.cancel_waiting_request()
                    self._last_start_error = (
                        result.message
                        or "Editing recovery could not reacquire WRITE."
                    )
                    return False

        self._collab_manager.resume_write_lease_renewal()
        self._expected_generation = self._collab_manager.get_lock_generation()
        self._finishing_started_at = None
        self._finishing_deadline = None
        self._publish_intent = False
        self._finishing_retry_count = 0
        self._state = WriteTransactionState.EDITING
        self._is_editing = True
        self._stale_editing_reason = ""
        self._last_start_error = ""
        if not self._open_local_mutations():
            return False
        logger.info(
            "Stale editing transaction recovered; expected_generation=%s",
            self._expected_generation,
        )
        return True

    # ---- Start / Finish / Cancel ----
    def start_editing(self, save_callback: Optional[Callable[[], bool]] = None) -> bool:
        start_total = time.perf_counter()
        self._last_start_error = ""
        self.reset_finishing()
        logger.info("Start Editing requested; transaction_state=%s", self._state.name)

        if self._state == WriteTransactionState.WAITING:
            self._last_start_error = "Already waiting for the active writer to release the lock."
            logger.info(self._last_start_error)
            return False

        if self._state != WriteTransactionState.IDLE:
            self._last_start_error = f"Start Editing is unavailable while transaction state is {self._state.name}."
            logger.warning(self._last_start_error)
            return False

        from centermanager.platform.write_recovery import WriteRecoveryJournal, require_replaceable, RecoveryRequired
        try:
            require_replaceable()
            receipt = WriteRecoveryJournal().inspect()
            self._pre_handoff_clean_receipt = (
                receipt if receipt is not None and receipt.get("status") == "CLEAN"
                else None
            )
        except RecoveryRequired as exc:
            self._last_start_error = str(exc)
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            return False
        if not self._transition_to(WriteTransactionState.ACQUIRING, "request write"):
            self._last_start_error = "Unable to enter write-lock acquisition state."
            return False

        request_started = time.perf_counter()
        result = self._collab_manager.request_write()
        request_ms = (time.perf_counter() - request_started) * 1000
        logger.info(
            "Start Editing collaboration result=%s message=%s position=%s",
            result.result.value,
            result.message,
            result.position,
        )
        if result.is_granted:
            # Immediate writers previously skipped the consistency barrier that
            # queued writers execute during handoff. Run it now while this
            # session owns the distributed lock; on failure, release the grant
            # before returning to IDLE.
            handoff_started = time.perf_counter()
            if not self._verify_first_writer_consistency():
                self._release_grant_after_failed_consistency_check()
                self._transition_to(WriteTransactionState.IDLE, "consistency verification failed")
                logger.info(
                    "PERF start_edit total_ms=%.1f request_ms=%.1f handoff_ms=%.1f result=consistency_failed",
                    (time.perf_counter() - start_total) * 1000,
                    request_ms,
                    (time.perf_counter() - handoff_started) * 1000,
                )
                return False
            handoff_ms = (time.perf_counter() - handoff_started) * 1000

            self._save_callback = save_callback
            self._has_changes = False
            self._session = self._collab_manager.get_session()

            self._expected_generation = self._collab_manager.get_lock_generation()
            logger.info(f"Expected generation captured: {self._expected_generation}")

            self._base_main_commit = self._get_handoff_main_commit()
            if self._base_main_commit is None and self._collab_manager._sync_provider:
                try:
                    # Compatibility fallback for older/custom sync services.
                    self._base_main_commit = (
                        self._collab_manager._sync_provider.get_remote_main_commit()
                    )
                except Exception as e:
                    logger.warning(f"Failed to capture base MAIN commit: {e}")
            logger.info(
                "Base MAIN commit captured: %s",
                self._base_main_commit[:8] if self._base_main_commit else None,
            )

            # Reject a GRANTED result whose lock disappeared during handoff.
            # Check before the durable journal and again just before the gate
            # opens to cover the several-second recovery capture window.
            if not self._verify_grant_before_editing():
                self._release_grant_after_failed_consistency_check()
                self._state = WriteTransactionState.IDLE
                return False
            if not self._begin_recovery_journal():
                self._release_grant_after_failed_consistency_check()
                return False
            if not self._verify_grant_before_editing():
                self._state = WriteTransactionState.RECOVERY_REQUIRED
                self._is_editing = False
                if self._recovery_journal is not None:
                    try:
                        self._recovery_journal.preserve("lost-authority-before-editing")
                        self._recovery_journal.update(mutation_authority_lost=True)
                    except Exception:
                        logger.exception("Failed to preserve recovery after WRITE grant loss")
                self._release_grant_after_failed_consistency_check()
                return False
            if not self._transition_to(WriteTransactionState.EDITING, "durable recovery prepared"):
                return False
            self._is_editing = True
            if not self._open_local_mutations():
                return False
            snapshot_started = time.perf_counter()
            self._create_snapshot()
            snapshot_ms = (time.perf_counter() - snapshot_started) * 1000
            logger.info(
                "PERF start_edit total_ms=%.1f request_ms=%.1f handoff_ms=%.1f snapshot_ms=%.1f",
                (time.perf_counter() - start_total) * 1000,
                request_ms,
                handoff_ms,
                snapshot_ms,
            )
            logger.info("Write transaction started: EDITING")
            return True
        elif result.is_waiting:
            if not self._waiting_is_authoritative():
                if not self._collab_manager.cancel_waiting_request():
                    self._transition_to(WriteTransactionState.WAITING, "cancellation acknowledgement pending")
                    self._waiting_request_id = result.request_id
                    self._waiting_started_at = datetime.now()
                    self._last_start_error = "Git request cancellation is pending verification."
                    return False
                self._transition_to(WriteTransactionState.IDLE, "false waiting rejected")
                self._last_start_error = (
                    "Unable to acquire the remote write lock even though no active writer owns it. "
                    "Check Git connectivity/credentials and try again."
                )
                logger.error(self._last_start_error)
                return False
            self._transition_to(WriteTransactionState.WAITING, "queued")
            self._waiting_position = result.position
            self._waiting_request_id = result.request_id
            self._waiting_started_at = datetime.now()
            self._last_start_error = result.message or f"Waiting for write lock (position {result.position})."
            logger.info(f"Write transaction waiting (position {result.position})")
            return False
        else:
            self._transition_to(WriteTransactionState.IDLE, "request rejected")
            self._last_start_error = result.message or "Write lock request was rejected."
            logger.warning(f"Failed to acquire write lock: {self._last_start_error}")
            return False

    def finish_editing(self,
                       save_callback: Optional[Callable[[], bool]] = None,
                       on_publish_success: Optional[Callable[[], None]] = None,
                       on_publish_failure: Optional[Callable[[str], None]] = None) -> bool:
        finish_total = time.perf_counter()
        if self._state == WriteTransactionState.IDLE:
            logger.warning("Finish editing called in IDLE state")
            return False

        if self._state == WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING:
            logger.info("Retrying authoritative WRITE lock release after successful publish")
            return self.retry_lock_release()

        if self._state == WriteTransactionState.WAITING:
            logger.warning("Finish editing called while waiting for lock")
            return False

        if self._state in (WriteTransactionState.FINISHING,
                           WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
                           WriteTransactionState.FINISHING_STALE,
                           WriteTransactionState.PUBLISH_CONFLICT):
            logger.warning(f"Finish editing called while already in {self._state.name}")
            return False

        if self._state == WriteTransactionState.COMPLETED:
            logger.warning("Transaction already completed")
            self._reset_to_idle()
            return True

        if self._mutation_gate is not None and self._mutation_gate.lost:
            return False
        self._report_warning = ""
        if self._mutation_gate is not None:
            with self._mutation_gate.lock:
                self._mutation_gate.finishing_thread = threading.get_ident()
        authority_started = time.perf_counter()
        result = self.enter_finishing()
        authority_ms = (time.perf_counter() - authority_started) * 1000
        if not result.get("success"):
            if self._state in (WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
                               WriteTransactionState.FINISHING_STALE,
                               WriteTransactionState.PUBLISH_CONFLICT):
                logger.warning(f"Cannot finish: {result.get('reason')}")
                return False
            else:
                logger.error(f"Unexpected failure entering finishing: {result.get('reason')}")
                return False

        save_started = time.perf_counter()
        save_fn = save_callback or self._save_callback
        if save_fn is not None:
            try:
                save_success = save_fn()
                if not save_success:
                    logger.error("Local save failed")
                    if self._state != WriteTransactionState.RECOVERY_REQUIRED:
                        self._state = WriteTransactionState.FAILED
                    if self._mutation_gate is not None:
                        self._mutation_gate.close()
                    return False
            except Exception:
                logger.exception("Local save exception")
                if self._state != WriteTransactionState.RECOVERY_REQUIRED:
                    self._state = WriteTransactionState.FAILED
                if self._mutation_gate is not None:
                    self._mutation_gate.close()
                return False

        if self._mutation_gate is not None:
            with self._mutation_gate.lock:
                if self._mutation_gate.lost:
                    return False
                self._mutation_gate.close()
                self._state = WriteTransactionState.LOCAL_SAVED
        else:
            self._state = WriteTransactionState.LOCAL_SAVED
        save_ms = (time.perf_counter() - save_started) * 1000
        self._on_publish_success = on_publish_success
        self._on_publish_failure = on_publish_failure

        if not self._create_pending_version():
            logger.error("Pending version creation failed")
            self._state = WriteTransactionState.FAILED
            return False

        materialize_started = time.perf_counter()
        if not self._publish_database_and_manifest():
            logger.error("Database + manifest publish failed")
            self._state = WriteTransactionState.FAILED
            if self._version_manager:
                self._version_manager.clear_pending_version()
            self._pending_version = None
            return False
        materialize_ms = (time.perf_counter() - materialize_started) * 1000

        publish_started = time.perf_counter()
        publish_result = self._publish()
        publish_ms = (time.perf_counter() - publish_started) * 1000
        logger.info(
            "PERF finish_edit total_ms=%.1f authority_ms=%.1f save_ms=%.1f materialize_ms=%.1f publish_release_ms=%.1f result=%s",
            (time.perf_counter() - finish_total) * 1000,
            authority_ms,
            save_ms,
            materialize_ms,
            publish_ms,
            "success" if publish_result else "failed",
        )
        return publish_result

    def cancel_editing(self, force: bool = False) -> bool:
        if self.is_waiting:
            if self._collab_manager.cancel_waiting_request():
                self._reset_to_idle()
                logger.info("Transaction: IDLE (cancelled waiting)")
                return True
            return False

        if not self.is_editing:
            logger.warning(f"Cancel editing in state {self._state}, ignoring")
            return False

        if self._has_changes and not force:
            logger.warning("Cancel called with pending changes, force=False")
            return False

        if self._mutation_gate is not None:
            self._mutation_gate.close()
        if self._recovery_journal is not None:
            try:
                self._recovery_journal.preserve("cancel-editing")
                self._recovery_journal.update(status="CANCELLED")
                self._state = WriteTransactionState.RECOVERY_REQUIRED
                self._is_editing = False
                if self._collab_manager.is_writing():
                    if not self._collab_manager.release_write():
                        self._last_start_error = "Cancelled data is preserved, but WRITE release is unverified. Keep recovery data and close CenterManager before reconciliation."
                        return False
                    self._recovery_journal.released()
                self._state = WriteTransactionState.RECOVERY_REQUIRED
                self._is_editing = False
                self._last_start_error = "Cancelled data is preserved. Inspect recovery and explicitly reconcile before synchronizing."
                return True
            except Exception as exc:
                self._state = WriteTransactionState.RECOVERY_REQUIRED
                self._is_editing = False
                self._last_start_error = f"Recovery preservation failed: {exc}. Free disk space and retry; keep the workspace."
                return False

        if force and self._has_changes:
            if not self._restore_snapshot():
                logger.error("Snapshot restore failed, lock retained")
                self._state = WriteTransactionState.FAILED
                return False

        if self._collab_manager.is_writing():
            if not self._collab_manager.release_write():
                return False
        self._delete_snapshot()
        self._reset_to_idle()
        logger.info("Transaction: IDLE (cancelled)")
        return True

    # ---- Publish helpers ----
    def _create_pending_version(self) -> bool:
        if self._version_manager is None:
            logger.warning("Version manager not set, skipping version increment")
            return True
        try:
            session = self._collab_manager.get_session()
            self._pending_version = self._version_manager.create_pending_version({
                "session_id": self._collab_manager.get_session_id(),
                "owner": session.username if session else "system",
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"Pending version created: {self._pending_version}")
            return True
        except Exception as e:
            logger.exception(f"Failed to create pending version: {e}")
            return False

    def _publish_database_and_manifest(self) -> bool:
        try:
            paths = get_paths()
            db_src = paths.database_dir / "center.db"
            if not db_src.exists():
                logger.warning("Database file not found, skipping copy")
                return True

            repo_root = paths.runtime_root / "repository"
            if not repo_root.exists():
                logger.warning("Repository not found, skipping copy")
                return True

            db_dst = repo_root / "database"
            db_dst.mkdir(parents=True, exist_ok=True)
            dst_file = db_dst / "center.db"

            # Capture checkpoint + source bytes under one maintenance fence, then
            # atomically install the immutable snapshot into the Git working tree.
            published_db = materialize_runtime_database_to_repository()
            if published_db != dst_file:
                raise RuntimeError("Authoritative publication returned an unexpected destination")
            logger.info("Database and signed identity published to repository from WAL-safe snapshot: %s", dst_file)

            if self._version_manager and self._pending_version:
                manifest_path = repo_root / "manifest.json"
                if not manifest_path.exists():
                    logger.error(f"Repository manifest not found: {manifest_path}")
                    return False
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                old_version = manifest.get("runtime_version")
                manifest["runtime_version"] = self._pending_version
                manifest["published_at"] = datetime.now().isoformat()
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                logger.info(f"Repository manifest updated from {old_version} to {self._pending_version}")

            return True
        except Exception as e:
            logger.exception(f"Failed to publish database: {e}")
            return False

    def _publish(self) -> bool:
        if self._state not in (WriteTransactionState.LOCAL_SAVED, WriteTransactionState.PUBLISHING):
            logger.warning(f"Publish called in invalid state {self._state}")
            return False

        self._state = WriteTransactionState.PUBLISHING

        try:
            if self._recovery_journal is not None:
                self._recovery_journal.preserve("before-publish")
                self._recovery_journal.update(status="PUBLISHING")
            success = self._do_publish()
            if success:
                if self._recovery_journal is not None:
                    self._recovery_journal.published(self._collab_manager._sync_provider)
                if self._version_manager:
                    self._version_manager.publish_pending_version()
                    self._pending_version = None
                self._state = WriteTransactionState.PUBLISHED
                if self._generate_reports is not None:
                    try:
                        self._generate_reports(set(self._dirty_student_ids))
                    except Exception as exc:
                        self._report_warning = (
                            f"Core data was published; local reports are incomplete. {exc}"
                        )
                        logger.exception("Published core data; derived report delivery failed")
                logger.info("Transaction: PUBLISHED")
                if self._on_publish_success:
                    self._on_publish_success()
                post_publish_pending = bool(self._recovery_journal is not None and
                    self._recovery_journal.preserve_post_publish_changes())
                self._collab_manager._lock.clear_finishing_data()
                self._finishing_deadline = None
                self._finishing_started_at = None
                self._publish_intent = False

                if not self._release_lock():
                    self._state = WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING
                    logger.warning(
                        "Transaction published successfully but remote WRITE lock release is pending"
                    )
                    return True

                if post_publish_pending:
                    self._state = WriteTransactionState.RECOVERY_REQUIRED
                    self._is_editing = False
                    self._last_start_error = "MAIN was published, but a post-publish callback saved additional local data. Recovery copies are retained; inspect and explicitly reconcile before further editing or synchronization."
                    return True
                self._delete_snapshot()
                self._reset_to_idle()
                return True
            else:
                self._state = WriteTransactionState.FAILED
                if self._version_manager:
                    self._version_manager.clear_pending_version()
                self._pending_version = None
                logger.error("Transaction: FAILED (publish returned False)")
                if self._on_publish_failure:
                    self._on_publish_failure("Publish operation failed (push failed)")
                return False
        except Exception as e:
            self._state = WriteTransactionState.RECOVERY_REQUIRED if self._recovery_journal is not None else WriteTransactionState.FAILED
            self._is_editing = False
            self._last_start_error = f"Local recovery remains protected: {e}. Keep the workspace and inspect recovery before synchronization."
            if self._version_manager:
                self._version_manager.clear_pending_version()
            self._pending_version = None
            logger.exception(f"Publish exception: {e}")
            if self._on_publish_failure:
                self._on_publish_failure(str(e))
            return False

    def _do_publish(self) -> bool:
        if self._sync_service:
            user = "system"
            session = self._collab_manager.get_session()
            if session and session.username:
                user = session.username
            publish_only = self._sync_service.publish_only
            kwargs = {
                "message": "Finish Editing",
                "user": user,
                "expected_main_commit": self._base_main_commit,
            }
            try:
                if "repository_already_materialized" in inspect.signature(
                    publish_only
                ).parameters:
                    kwargs["repository_already_materialized"] = True
            except (TypeError, ValueError):
                pass
            return publish_only(**kwargs)
        logger.warning("No sync service available for publish")
        return False

    def _release_lock(self) -> bool:
        if not self._collab_manager.is_writing():
            logger.warning("Cannot confirm transaction completion: local WRITE ownership is absent")
            return False
        if not self._collab_manager.release_write():
            logger.warning("Remote WRITE lock release is not yet confirmed")
            return False
        if self._recovery_journal is not None:
            self._recovery_journal.released()
        self._state = WriteTransactionState.COMPLETED
        logger.info("Transaction: COMPLETED (lock released)")
        return True

    def retry_lock_release(self) -> bool:
        """Retry only the authoritative lock release after MAIN is already published."""
        if self._state != WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING:
            return False
        if not self._release_lock():
            return False
        if self._recovery_journal is not None and self._recovery_journal.inspect()['status'] == 'POST_PUBLISH_PENDING':
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            self._is_editing = False
            self._last_start_error = "Published MAIN and released WRITE; additional local data is preserved for explicit recovery reconciliation."
            return True
        self._delete_snapshot()
        self._reset_to_idle()
        return True

    # ---- Retry / Offline ----
    def retry_publish(self) -> bool:
        if self._state not in (WriteTransactionState.FAILED, WriteTransactionState.OFFLINE_PENDING_PUBLISH):
            logger.warning(f"Retry called in state {self._state}, ignoring")
            return False
        if self._pending_version is None:
            logger.warning("Retry called but no pending version to publish")
            return False
        logger.info("Retrying publish...")
        self._state = WriteTransactionState.LOCAL_SAVED
        return self._publish()

    def continue_offline(self) -> bool:
        if self._state != WriteTransactionState.FAILED:
            logger.warning(f"Continue offline called in state {self._state}, ignoring")
            return False
        self._state = WriteTransactionState.OFFLINE_PENDING_PUBLISH
        logger.info("Transaction: OFFLINE_PENDING_PUBLISH")
        return True

    def get_waiting_position(self) -> int:
        return self._waiting_position

    def get_waiting_started_at(self) -> Optional[datetime]:
        return self._waiting_started_at

    def cancel_waiting(self, reason: str = "Waiting request expired or was removed") -> None:
        """Leave WAITING when the collaboration layer no longer owns our request."""
        if self._state != WriteTransactionState.WAITING:
            return
        logger.warning(f"Transaction: WAITING -> IDLE ({reason})")
        self._state = WriteTransactionState.IDLE
        self._waiting_position = 0
        self._waiting_request_id = ""
        self._waiting_started_at = None
        self._is_editing = False
        self._session = None

    def begin_grant(self) -> bool:
        """Enter GRANTING while the collaboration layer completes a handoff."""
        if self._state != WriteTransactionState.WAITING:
            return False
        return self._transition_to(WriteTransactionState.GRANTING, "remote handoff")

    def on_write_granted(self) -> None:
        """Apply an authoritative remote write grant exactly once."""
        if self._state == WriteTransactionState.EDITING:
            logger.debug("Duplicate write grant ignored: transaction already EDITING")
            return

        if self._state not in (
            WriteTransactionState.WAITING,
            WriteTransactionState.GRANTING,
        ):
            logger.debug(
                "Write grant ignored in non-grantable state %s",
                self._state.name,
            )
            return

        if self._state == WriteTransactionState.WAITING:
            if not self._transition_to(
                WriteTransactionState.GRANTING,
                "remote grant observed",
            ):
                return

        self._is_editing = False
        self._session = self._collab_manager.get_session()
        self._expected_generation = self._collab_manager.get_lock_generation()

        self._base_main_commit = self._get_handoff_main_commit()
        if self._base_main_commit is None and self._collab_manager._sync_provider:
            try:
                self._base_main_commit = (
                    self._collab_manager._sync_provider.get_remote_main_commit()
                )
            except Exception:
                pass

        if not self._verify_grant_before_editing():
            self._release_grant_after_failed_consistency_check()
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            return
        if not self._begin_recovery_journal():
            self._release_grant_after_failed_consistency_check()
            return
        if not self._verify_grant_before_editing():
            self._state = WriteTransactionState.RECOVERY_REQUIRED
            self._is_editing = False
            if self._recovery_journal is not None:
                try:
                    self._recovery_journal.preserve("lost-authority-before-editing")
                    self._recovery_journal.update(mutation_authority_lost=True)
                except Exception:
                    logger.exception("Failed to preserve recovery after queued WRITE grant loss")
            self._release_grant_after_failed_consistency_check()
            return
        if not self._transition_to(WriteTransactionState.EDITING, "durable recovery prepared"):
            return
        self._is_editing = True
        if not self._open_local_mutations():
            return
        self._waiting_position = 0
        self._waiting_request_id = ""
        self._waiting_started_at = None
        self._create_snapshot()

        logger.info(
            "Transaction: WAITING/GRANTING -> EDITING (auto-grant), expected gen: %s",
            self._expected_generation,
        )

    def on_grant_failed(self) -> None:
        """Return from GRANTING to WAITING when authoritative acquisition fails."""
        if self._state == WriteTransactionState.GRANTING:
            self._transition_to(WriteTransactionState.WAITING, "grant failed")

    # ---- Finishing methods ----
    def enter_finishing(self) -> Dict[str, Any]:
        if self._state not in (WriteTransactionState.EDITING, WriteTransactionState.LOCAL_SAVED):
            return {"success": False, "reason": f"Invalid state for finishing: {self._state.name}"}

        session = self._collab_manager.get_session()
        if not session:
            return {"success": False, "reason": "No active session"}

        if not self._collab_manager.is_collaboration_available():
            self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
            reason = "Collaboration unavailable"
            logger.warning(f"Entered FINISHING_WAITING_FOR_COLLABORATION due to: {reason}")
            return {"success": False, "reason": reason, "state": "WAITING_FOR_COLLABORATION"}

        auth = self._collab_manager.validate_write_authority(session)
        if self._mutation_gate is not None and self._mutation_gate.lost:
            return {"success": False, "reason": self._last_start_error}

        if not auth.get("valid", False):
            reason = auth.get("reason", "Unknown authority failure")
            if "unavailable" in reason.lower():
                self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
                logger.warning(f"Entered FINISHING_WAITING_FOR_COLLABORATION due to: {reason}")
                return {"success": False, "reason": reason, "state": "WAITING_FOR_COLLABORATION"}
            else:
                self._state = WriteTransactionState.FINISHING_STALE
                logger.warning(f"Entered FINISHING_STALE due to: {reason}")
                return {"success": False, "reason": reason, "state": "STALE"}

        if auth.get("generation_authoritative") is True:
            current_gen = int(auth.get("generation", 0) or 0)
        else:
            # Compatibility fallback for test doubles/custom collaboration
            # implementations that do not explicitly certify the generation
            # as coming from the same authoritative remote-lock observation.
            current_gen = self._collab_manager.get_lock_generation()
        if current_gen != self._expected_generation:
            reason = f"Generation mismatch: expected {self._expected_generation}, current {current_gen}"
            self._state = WriteTransactionState.FINISHING_STALE
            logger.warning(f"Entered FINISHING_STALE due to: {reason}")
            return {"success": False, "reason": reason, "state": "STALE"}

        if self._collab_manager._sync_provider:
            try:
                provider = self._collab_manager._sync_provider
                observe_remote = self._explicit_method(
                    provider,
                    "observe_remote_main_commit",
                )
                current_main = (
                    observe_remote()
                    if observe_remote is not None
                    else provider.get_remote_main_commit()
                )
                if current_main is None:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = "MAIN verification failed: cannot get remote commit"
                    logger.warning(f"Entered PUBLISH_CONFLICT due to: {reason}")
                    return {"success": False, "reason": reason, "state": "CONFLICT"}

                if self._base_main_commit is not None and current_main != self._base_main_commit:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = f"MAIN conflict: base={self._base_main_commit[:8]}, current={current_main[:8]}"
                    logger.warning(f"Entered PUBLISH_CONFLICT due to: {reason}")
                    return {"success": False, "reason": reason, "state": "CONFLICT"}

                if self._base_main_commit is None:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = "MAIN base unknown: cannot verify concurrency"
                    logger.warning(f"Entered PUBLISH_CONFLICT due to: {reason}")
                    return {"success": False, "reason": reason, "state": "CONFLICT"}

            except Exception as e:
                self._state = WriteTransactionState.PUBLISH_CONFLICT
                reason = f"MAIN verification unavailable: {e}"
                logger.warning(f"Entered PUBLISH_CONFLICT due to: {reason}")
                return {"success": False, "reason": reason, "state": "CONFLICT"}

        now = datetime.now()
        deadline = now + timedelta(seconds=120)
        self._finishing_started_at = now
        self._finishing_deadline = deadline
        self._publish_intent = True
        self._finishing_retry_count = 0

        self._collab_manager._lock.set_finishing_data(now, deadline, True)
        self._state = WriteTransactionState.FINISHING

        logger.info(f"Entered FINISHING: started={now}, deadline={deadline}")
        return {
            "success": True,
            "reason": "OK",
            "state": "FINISHING",
            "deadline": deadline,
        }

    def refresh_finishing_authority(self) -> Dict[str, Any]:
        if self._state not in (
            WriteTransactionState.FINISHING,
            WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
        ):
            return {"success": False, "reason": f"Not in finishing state: {self._state.name}"}

        if (
            self._state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
            and self._finishing_deadline
            and datetime.now() >= self._finishing_deadline
        ):
            self._state = WriteTransactionState.FINISHING_STALE
            logger.warning("Finishing deadline expired while waiting -> FINISHING_STALE")
            return {"success": False, "reason": "Deadline expired", "state": "STALE"}

        if not self._collab_manager.is_collaboration_available():
            if self._state != WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION:
                self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
                logger.warning("Collaboration unavailable -> FINISHING_WAITING_FOR_COLLABORATION")
            return {
                "success": False,
                "reason": "Collaboration unavailable",
                "state": "WAITING_FOR_COLLABORATION",
            }

        if self._state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION:
            self._state = WriteTransactionState.FINISHING
            logger.info("Collaboration restored -> FINISHING")

        if self._finishing_deadline and datetime.now() >= self._finishing_deadline:
            self._state = WriteTransactionState.FINISHING_STALE
            logger.warning("Finishing deadline expired -> FINISHING_STALE")
            return {"success": False, "reason": "Deadline expired", "state": "STALE"}

        session = self._collab_manager.get_session()
        if not session:
            self._state = WriteTransactionState.FINISHING_STALE
            return {"success": False, "reason": "No session", "state": "STALE"}

        auth = self._collab_manager.validate_write_authority(session)
        if self._mutation_gate is not None and self._mutation_gate.lost:
            return {"success": False, "reason": self._last_start_error}

        if auth.get("valid", False):
            current_gen = self._collab_manager.get_lock_generation()
            if current_gen != self._expected_generation:
                self._state = WriteTransactionState.FINISHING_STALE
                reason = (
                    f"Generation mismatch: expected {self._expected_generation}, "
                    f"current {current_gen}"
                )
                return {"success": False, "reason": reason, "state": "STALE"}

            if self._base_main_commit and self._collab_manager._sync_provider:
                try:
                    current_main = self._collab_manager._sync_provider.get_remote_main_commit()
                except Exception as e:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = f"MAIN verification unavailable: {e}"
                    return {"success": False, "reason": reason, "state": "CONFLICT"}
                if current_main is None:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = "MAIN verification failed: cannot get remote commit"
                    return {"success": False, "reason": reason, "state": "CONFLICT"}
                if current_main != self._base_main_commit:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = (
                        f"MAIN conflict: base={self._base_main_commit[:8]}, "
                        f"current={current_main[:8]}"
                    )
                    return {"success": False, "reason": reason, "state": "CONFLICT"}

            return {"success": True, "reason": "Authority valid", "state": self._state.name}

        reason = auth.get("reason", "Unknown")
        if "unavailable" in reason.lower():
            self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
            return {
                "success": False,
                "reason": reason,
                "state": "WAITING_FOR_COLLABORATION",
            }

        provider = getattr(self._collab_manager, "_sync_provider", None)
        if (
            "lease expired or missing" in reason.lower()
            and provider is not None
            and self._base_main_commit
        ):
            try:
                remote = provider.remote_lock_status()
                if (
                    isinstance(remote, dict)
                    and remote.get("locked")
                    and remote.get("session_id") == session.session_id
                    and remote.get("lock_generation") == self._expected_generation
                ):
                    try:
                        current_main = provider.get_remote_main_commit()
                    except Exception as exc:
                        self._state = WriteTransactionState.PUBLISH_CONFLICT
                        return {
                            "success": False,
                            "reason": f"MAIN verification unavailable: {exc}",
                            "state": "CONFLICT",
                        }
                    if current_main is None or current_main != self._base_main_commit:
                        self._state = WriteTransactionState.PUBLISH_CONFLICT
                        return {
                            "success": False,
                            "reason": "MAIN verification failed",
                            "state": "CONFLICT",
                        }
            except Exception:
                pass

        self._state = WriteTransactionState.FINISHING_STALE
        logger.warning(f"Authority invalid -> FINISHING_STALE: {reason}")
        return {"success": False, "reason": reason, "state": "STALE"}

    def is_finishing_deadline_expired(self) -> bool:
        if self._finishing_deadline is None:
            return False
        return datetime.now() >= self._finishing_deadline

    def reset_finishing(self) -> None:
        """Reset local finishing state and collaboration finishing metadata."""
        self._is_finishing = False

        if self._collab_manager is None:
            return

        clear_remote = getattr(
            self._collab_manager,
            "clear_finishing_data",
            None,
        )

        if callable(clear_remote):
            clear_remote()
            return

        remote_lock = getattr(self._collab_manager, "_lock", None)
        clear_lock_data = getattr(
            remote_lock,
            "clear_finishing_data",
            None,
        )

        if callable(clear_lock_data):
            clear_lock_data()
