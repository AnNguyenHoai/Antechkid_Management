# -*- coding: utf-8 -*-
"""WriteTransaction - Complete write transaction for Student Workspace."""
import logging
import shutil
import json
import os
from enum import Enum, auto
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.core.paths import get_paths
from centermanager.platform.collaboration import CollaborationManager, WriteRequestResult

logger = logging.getLogger(__name__)


class WriteTransactionState(Enum):
    """State machine for write transaction."""
    IDLE = auto()
    EDITING = auto()
    LOCAL_SAVED = auto()
    PUBLISHING = auto()
    PUBLISHED = auto()
    COMPLETED = auto()
    FAILED = auto()
    OFFLINE_PENDING_PUBLISH = auto()
    WAITING = auto()
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
        self._pending_version: Optional[int] = None
        self._snapshot_path: Optional[Path] = None
        self._waiting_position: int = 0
        self._waiting_request_id: str = ""
        self._session = None

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

    def set_sync_service(self, sync_service) -> None:
        self._sync_service = sync_service

    def set_version_manager(self, version_manager) -> None:
        self._version_manager = version_manager

    def mark_dirty(self) -> None:
        self._has_changes = True

    def _reset_to_idle(self) -> None:
        """Reset transaction state to IDLE after completion."""
        self._state = WriteTransactionState.IDLE
        self._session = None
        self._save_callback = None
        self._on_publish_success = None
        self._on_publish_failure = None
        self._has_changes = False
        self._pending_version = None
        self._snapshot_path = None
        self._waiting_position = 0
        self._waiting_request_id = ""
        self._finishing_started_at = None
        self._finishing_deadline = None
        self._publish_intent = False
        self._finishing_retry_count = 0
        self._expected_generation = 0
        self._base_main_commit = None
        self._is_editing = False
        logger.info("Transaction reset to IDLE")

    # ---- Snapshot ----
    def _create_snapshot(self) -> None:
        try:
            paths = get_paths()
            db_path = paths.database_dir / "center.db"
            if db_path.exists():
                snapshot_dir = paths.runtime_root / "snapshots"
                snapshot_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                snapshot_path = snapshot_dir / f"pre_edit_{timestamp}.db"
                shutil.copy2(db_path, snapshot_path)
                self._snapshot_path = snapshot_path
                logger.info(f"Snapshot created at {snapshot_path}")
        except Exception as e:
            logger.exception("Failed to create snapshot")

    def _restore_snapshot(self) -> bool:
        if self._snapshot_path and self._snapshot_path.exists():
            try:
                paths = get_paths()
                db_path = paths.database_dir / "center.db"
                shutil.copy2(self._snapshot_path, db_path)
                logger.info("Snapshot restored")
                return True
            except Exception as e:
                logger.exception("Failed to restore snapshot")
        return False

    # ---- Start / Finish / Cancel ----
    def start_editing(self, save_callback: Optional[Callable[[], bool]] = None) -> bool:
        self.reset_finishing()

        if self._state == WriteTransactionState.WAITING:
            logger.info("Already waiting for write lock")
            return False

        if self._state != WriteTransactionState.IDLE:
            logger.warning(f"Start editing called in state {self._state}, ignoring")
            return False

        result = self._collab_manager.request_write()
        if result.is_granted:
            self._state = WriteTransactionState.EDITING
            self._save_callback = save_callback
            self._has_changes = False
            self._session = self._collab_manager.get_session()
            self._is_editing = True

            # Capture expected generation
            self._expected_generation = self._collab_manager._lock.get_lock_generation()
            logger.info(f"Expected generation captured: {self._expected_generation}")

            # Capture base MAIN commit for optimistic concurrency
            self._base_main_commit = None
            if self._collab_manager._sync_provider:
                try:
                    self._base_main_commit = self._collab_manager._sync_provider.get_remote_main_commit()
                    logger.info(f"Base MAIN commit captured: {self._base_main_commit[:8] if self._base_main_commit else None}")
                except Exception as e:
                    logger.warning(f"Failed to capture base MAIN commit: {e}")

            self._create_snapshot()
            logger.info("Write transaction started: EDITING")
            return True
        elif result.is_waiting:
            self._state = WriteTransactionState.WAITING
            self._waiting_position = result.position
            self._waiting_request_id = result.request_id
            logger.info(f"Write transaction waiting (position {result.position})")
            return False
        else:
            logger.warning(f"Failed to acquire write lock: {result.message}")
            return False

    def finish_editing(self,
                       save_callback: Optional[Callable[[], bool]] = None,
                       on_publish_success: Optional[Callable[[], None]] = None,
                       on_publish_failure: Optional[Callable[[str], None]] = None) -> bool:
        if self._state == WriteTransactionState.IDLE:
            logger.warning("Finish editing called in IDLE state")
            return False

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

        # Try to enter FINISHING (which includes all validations)
        result = self.enter_finishing()
        if not result.get("success"):
            if self._state in (WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
                               WriteTransactionState.FINISHING_STALE,
                               WriteTransactionState.PUBLISH_CONFLICT):
                logger.warning(f"Cannot finish: {result.get('reason')}")
                return False
            else:
                logger.error(f"Unexpected failure entering finishing: {result.get('reason')}")
                return False

        # Now in FINISHING state
        save_fn = save_callback or self._save_callback
        if save_fn is not None:
            try:
                save_success = save_fn()
                if not save_success:
                    logger.error("Local save failed")
                    self._state = WriteTransactionState.FAILED
                    return False
            except Exception as e:
                logger.exception("Local save exception")
                self._state = WriteTransactionState.FAILED
                return False

        self._state = WriteTransactionState.LOCAL_SAVED
        self._on_publish_success = on_publish_success
        self._on_publish_failure = on_publish_failure

        # Create pending version
        if not self._create_pending_version():
            logger.error("Pending version creation failed")
            self._state = WriteTransactionState.FAILED
            return False

        # Publish database + manifest
        if not self._publish_database_and_manifest():
            logger.error("Database + manifest publish failed")
            self._state = WriteTransactionState.FAILED
            return False

        # Perform actual publish (commit+push)
        return self._publish()

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

        if force and self._has_changes:
            if not self._restore_snapshot():
                logger.error("Snapshot restore failed, lock retained")
                self._state = WriteTransactionState.FAILED
                return False

        if self._collab_manager.is_writing():
            self._collab_manager.release_write()
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

            with open(db_src, 'rb') as fsrc:
                with open(dst_file, 'wb') as fdst:
                    fdst.write(fsrc.read())
                    fdst.flush()
                    os.fsync(fdst.fileno())

            if dst_file.exists() and db_src.exists():
                src_size = db_src.stat().st_size
                dst_size = dst_file.stat().st_size
                if src_size != dst_size:
                    logger.error(f"Size mismatch after copy: src={src_size}, dst={dst_size}")
                    return False
            logger.info(f"Database copied to repository: {dst_file}")

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
            success = self._do_publish()
            if success:
                if self._version_manager:
                    self._version_manager.publish_pending_version()
                    self._pending_version = None
                self._state = WriteTransactionState.PUBLISHED
                logger.info("Transaction: PUBLISHED")
                if self._on_publish_success:
                    self._on_publish_success()
                # Clear finishing data on success
                self._collab_manager._lock.clear_finishing_data()
                self._finishing_deadline = None
                self._finishing_started_at = None
                self._publish_intent = False
                self._release_lock()
                self._reset_to_idle()
                return True
            else:
                # Keep the pending version and local commit intact so the exact
                # same publication can be retried after a transient/conflict failure.
                self._state = WriteTransactionState.OFFLINE_PENDING_PUBLISH
                logger.info("Transaction: OFFLINE_PENDING_PUBLISH (publish failed; pending version retained)")
                if self._on_publish_failure:
                    self._on_publish_failure("Publish operation failed (push failed)")
                return False
        except Exception as e:
            # A failed push is retryable. Do not clear the pending version or
            # release the write lock here.
            self._state = WriteTransactionState.OFFLINE_PENDING_PUBLISH
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
            return self._sync_service.publish_only(message="Finish Editing", user=user, expected_main_commit=self._base_main_commit)
        logger.warning("No sync service available for publish")
        return False

    def _release_lock(self) -> None:
        if self._collab_manager.is_writing():
            self._collab_manager.release_write()
            self._state = WriteTransactionState.COMPLETED
            logger.info("Transaction: COMPLETED (lock released)")

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

    def cancel_waiting(self, reason: str = "Waiting request expired or was removed") -> None:
        """Leave WAITING when the collaboration layer no longer owns our request.

        This is intentionally narrower than cancel_editing(): a waiting
        transaction has no business edits or snapshot to roll back.
        """
        if self._state != WriteTransactionState.WAITING:
            return
        logger.warning(f"Transaction: WAITING -> IDLE ({reason})")
        self._state = WriteTransactionState.IDLE
        self._waiting_position = 0
        self._waiting_request_id = ""
        self._is_editing = False
        self._session = None

    def on_write_granted(self) -> None:
        """
        Called when write lock is granted to a waiting session (auto-grant).
        This is the callback from CollaborationManager when auto-grant succeeds.
        """
        if self._state == WriteTransactionState.WAITING:
            self._state = WriteTransactionState.EDITING
            self._is_editing = True
            self._session = self._collab_manager.get_session()
            # Capture expected generation
            self._expected_generation = self._collab_manager._lock.get_lock_generation()
            # Capture base MAIN commit
            self._base_main_commit = None
            if self._collab_manager._sync_provider:
                try:
                    self._base_main_commit = self._collab_manager._sync_provider.get_remote_main_commit()
                except Exception:
                    pass
            # Reset waiting position
            self._waiting_position = 0
            self._waiting_request_id = ""
            # Create snapshot for the new session
            self._create_snapshot()
            logger.info(f"Transaction: WAITING -> EDITING (auto-grant), expected gen: {self._expected_generation}")
        else:
            logger.warning(f"on_write_granted called in state {self._state}, ignoring")

    # ---- Finishing methods ----
    def enter_finishing(self) -> Dict[str, Any]:
        if self._state not in (WriteTransactionState.EDITING, WriteTransactionState.LOCAL_SAVED):
            return {"success": False, "reason": f"Invalid state for finishing: {self._state.name}"}

        session = self._collab_manager.get_session()
        if not session:
            return {"success": False, "reason": "No active session"}

        # 1. Validate collaboration authority (includes availability, lease, heartbeat)
        auth = self._collab_manager.validate_write_authority(session)

        if not auth.get("valid", False):
            reason = auth.get("reason", "Unknown authority failure")

            # Check for collaboration unavailable specifically
            if "unavailable" in reason.lower():
                self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
                logger.warning(f"Entered FINISHING_WAITING_FOR_COLLABORATION due to: {reason}")
                return {"success": False, "reason": reason, "state": "WAITING_FOR_COLLABORATION"}
            else:
                self._state = WriteTransactionState.FINISHING_STALE
                logger.warning(f"Entered FINISHING_STALE due to: {reason}")
                return {"success": False, "reason": reason, "state": "STALE"}

        # 2. Generation fencing
        current_gen = self._collab_manager._lock.get_lock_generation()
        if current_gen != self._expected_generation:
            reason = f"Generation mismatch: expected {self._expected_generation}, current {current_gen}"
            self._state = WriteTransactionState.FINISHING_STALE
            logger.warning(f"Entered FINISHING_STALE due to: {reason}")
            return {"success": False, "reason": reason, "state": "STALE"}

        # 3. MAIN optimistic concurrency
        if self._collab_manager._sync_provider:
            try:
                current_main = self._collab_manager._sync_provider.get_remote_main_commit()
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

        # All validations passed - enter FINISHING
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
        if self._state not in (WriteTransactionState.FINISHING,
                               WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION):
            return {"success": False, "reason": f"Not in finishing state: {self._state.name}"}

        # Check if deadline expired
        if self._finishing_deadline and datetime.now() >= self._finishing_deadline:
            self._state = WriteTransactionState.FINISHING_STALE
            logger.warning("Finishing deadline expired -> FINISHING_STALE")
            return {"success": False, "reason": "Deadline expired", "state": "STALE"}

        session = self._collab_manager.get_session()
        if not session:
            self._state = WriteTransactionState.FINISHING_STALE
            return {"success": False, "reason": "No session", "state": "STALE"}

        # Validate authority
        auth = self._collab_manager.validate_write_authority(session)

        if auth.get("valid", False):
            # Still valid, check generation against expected
            current_gen = self._collab_manager._lock.get_lock_generation()
            if current_gen != self._expected_generation:
                self._state = WriteTransactionState.FINISHING_STALE
                reason = f"Generation mismatch: expected {self._expected_generation}, current {current_gen}"
                logger.warning(f"Authority refresh failed: {reason}")
                return {"success": False, "reason": reason, "state": "STALE"}

            # Check MAIN concurrency
            if self._base_main_commit and self._collab_manager._sync_provider:
                try:
                    current_main = self._collab_manager._sync_provider.get_remote_main_commit()
                    if current_main is None:
                        self._state = WriteTransactionState.PUBLISH_CONFLICT
                        reason = "MAIN verification failed: cannot get remote commit"
                        logger.warning(f"Authority refresh -> PUBLISH_CONFLICT: {reason}")
                        return {"success": False, "reason": reason, "state": "CONFLICT"}
                    if current_main != self._base_main_commit:
                        self._state = WriteTransactionState.PUBLISH_CONFLICT
                        reason = f"MAIN conflict: base={self._base_main_commit[:8]}, current={current_main[:8]}"
                        logger.warning(f"Authority refresh -> PUBLISH_CONFLICT: {reason}")
                        return {"success": False, "reason": reason, "state": "CONFLICT"}
                except Exception as e:
                    self._state = WriteTransactionState.PUBLISH_CONFLICT
                    reason = f"MAIN verification unavailable: {e}"
                    logger.warning(f"Authority refresh -> PUBLISH_CONFLICT: {reason}")
                    return {"success": False, "reason": reason, "state": "CONFLICT"}

            if self._state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION:
                self._state = WriteTransactionState.FINISHING
                logger.info("Collaboration restored and generation valid -> back to FINISHING")
            return {"success": True, "reason": "Authority valid", "state": self._state.name}

        reason = auth.get("reason", "Unknown")
        if "unavailable" in reason.lower():
            if self._state != WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION:
                self._state = WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION
                logger.warning(f"Collaboration unavailable -> FINISHING_WAITING_FOR_COLLABORATION: {reason}")
            return {"success": False, "reason": reason, "state": "WAITING_FOR_COLLABORATION"}

        self._state = WriteTransactionState.FINISHING_STALE
        logger.warning(f"Authority invalid -> FINISHING_STALE: {reason}")
        return {"success": False, "reason": reason, "state": "STALE"}
    def is_finishing_deadline_expired(self) -> bool:
        if self._finishing_deadline is None:
            return False
        return datetime.now() >= self._finishing_deadline

    def reset_finishing(self) -> None:
        self._finishing_started_at = None
        self._finishing_deadline = None
        self._publish_intent = False
        self._finishing_retry_count = 0
        if self._collab_manager and hasattr(self._collab_manager, '_lock'):
            self._collab_manager._lock.clear_finishing_data()
        if self._state in (WriteTransactionState.FINISHING,
                           WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
                           WriteTransactionState.FINISHING_STALE):
            self._state = WriteTransactionState.EDITING
        logger.info("Finishing state reset to EDITING")