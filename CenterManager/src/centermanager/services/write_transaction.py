# -*- coding: utf-8 -*-
"""WriteTransaction - Complete write transaction for Student Workspace."""

import logging
import shutil
from enum import Enum, auto
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime
import os, json
from centermanager.core.paths import get_paths
from centermanager.platform.collaboration import CollaborationManager

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


class WriteTransactionManager:
    """
    Manages complete write transaction: Start Editing → Finish Editing.
    """

    def __init__(self, collaboration_manager: CollaborationManager):
        self._collab = collaboration_manager
        self._state = WriteTransactionState.IDLE
        self._save_callback: Optional[Callable[[], bool]] = None
        self._on_publish_success: Optional[Callable[[], None]] = None
        self._on_publish_failure: Optional[Callable[[str], None]] = None
        self._sync_service = None
        self._version_manager = None
        self._has_changes = False
        self._pending_version: Optional[int] = None
        self._snapshot_path: Optional[Path] = None

    @property
    def state(self) -> WriteTransactionState:
        return self._state

    @property
    def is_editing(self) -> bool:
        return self._state in (WriteTransactionState.EDITING, WriteTransactionState.LOCAL_SAVED)

    @property
    def can_edit(self) -> bool:
        return self._state == WriteTransactionState.IDLE

    def set_sync_service(self, sync_service) -> None:
        """Inject sync service for publishing."""
        self._sync_service = sync_service

    def set_version_manager(self, version_manager) -> None:
        """Inject version manager for runtime version increment."""
        self._version_manager = version_manager

    def mark_dirty(self) -> None:
        """Mark that local changes exist."""
        self._has_changes = True

    def has_changes(self) -> bool:
        return self._has_changes

    def start_editing(self, save_callback: Optional[Callable[[], bool]] = None) -> bool:
        """Begin edit session. Acquire write lock and create snapshot."""
        if self._state != WriteTransactionState.IDLE:
            logger.warning(f"Start editing called in state {self._state}, ignoring")
            return False

        if self._collab.request_write():
            self._state = WriteTransactionState.EDITING
            self._save_callback = save_callback
            self._has_changes = False
            self._create_snapshot()
            logger.info("Write transaction started: EDITING")
            return True

        logger.warning("Failed to acquire write lock")
        return False

    def finish_editing(
        self,
        save_callback: Optional[Callable[[], bool]] = None,
        on_publish_success: Optional[Callable[[], None]] = None,
        on_publish_failure: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Complete the edit session: save, publish, release lock."""
        if self._state == WriteTransactionState.IDLE:
            logger.warning("Finish editing called in IDLE state")
            return False

        if self._state == WriteTransactionState.COMPLETED:
            logger.warning("Transaction already completed")
            return True

        save_fn = save_callback or self._save_callback
        self._on_publish_success = on_publish_success
        self._on_publish_failure = on_publish_failure

        # 1. Save local changes
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
        logger.info("Transaction: LOCAL_SAVED")

        # 2. Create pending version
        if not self._create_pending_version():
            logger.error("Pending version creation failed")
            self._state = WriteTransactionState.FAILED
            return False

        # 3. Copy database AND update manifest in repository
        if not self._publish_database_and_manifest():
            logger.error("Database + manifest publish failed")
            self._state = WriteTransactionState.FAILED
            return False

        # 4. Publish (commit + push)
        return self._publish()

    def _create_snapshot(self) -> None:
        """Create a snapshot of the database for rollback."""
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
        """Restore database from snapshot."""
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

    def _publish_database_and_manifest(self) -> bool:
        """
        Copy database to repository AND update repository manifest.
        This MUST happen BEFORE Git commit.
        """
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

            # 1. Copy database using binary read/write
            db_dst = repo_root / "database"
            db_dst.mkdir(parents=True, exist_ok=True)
            dst_file = db_dst / "center.db"
            
            with open(db_src, 'rb') as fsrc:
                with open(dst_file, 'wb') as fdst:
                    fdst.write(fsrc.read())
                    fdst.flush()
                    os.fsync(fdst.fileno())
            
            # Verify
            if dst_file.exists() and db_src.exists():
                src_size = db_src.stat().st_size
                dst_size = dst_file.stat().st_size
                logger.info(f"Database copied: src_size={src_size}, dst_size={dst_size}")
                if src_size != dst_size:
                    logger.error(f"Size mismatch after copy: src={src_size}, dst={dst_size}")
                    return False
            else:
                logger.error("Copy failed: destination file missing")
                return False
                
            logger.info(f"Database copied to repository: {dst_file}")

            # 2. Update repository manifest with pending version
            if self._version_manager and self._pending_version:
                manifest_path = repo_root / "manifest.json"
                if not manifest_path.exists():
                    logger.error(f"Repository manifest not found: {manifest_path}")
                    return False

                # Read existing manifest
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                old_version = manifest.get("runtime_version")
                manifest["runtime_version"] = self._pending_version
                manifest["published_at"] = datetime.now().isoformat()
                
                # Write new manifest
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                
                logger.info(f"Repository manifest updated from version {old_version} to {self._pending_version}")
                
                # Verify file content
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    verify = json.load(f)
                logger.info(f"Manifest verification: runtime_version={verify.get('runtime_version')}")

            return True
        except Exception as e:
            logger.exception(f"Failed to publish database: {e}")
            return False

    def _create_pending_version(self) -> bool:
        """Create pending version."""
        if self._version_manager is None:
            logger.warning("Version manager not set, skipping version increment")
            return True

        try:
            self._pending_version = self._version_manager.create_pending_version({
                "session_id": self._collab.get_session_id(),
                "owner": self._collab.get_session().username if self._collab.get_session() else "system",
                "timestamp": datetime.now().isoformat(),
            })
            logger.info(f"Pending version created: {self._pending_version}")
            return True
        except Exception as e:
            logger.exception(f"Failed to create pending version: {e}")
            return False

    def _publish(self) -> bool:
        """Execute publish and handle result."""
        if self._state not in (WriteTransactionState.LOCAL_SAVED, WriteTransactionState.PUBLISHING):
            logger.warning(f"Publish called in invalid state {self._state}")
            return False

        self._state = WriteTransactionState.PUBLISHING

        try:
            success = self._do_publish()
            if success:
                # Publish pending version
                if self._version_manager:
                    self._version_manager.publish_pending_version()
                    self._pending_version = None
                self._state = WriteTransactionState.PUBLISHED
                logger.info("Transaction: PUBLISHED")
                if self._on_publish_success:
                    self._on_publish_success()
                self._release_lock()
                return True
            else:
                # Push failed: rollback pending version
                if self._version_manager:
                    self._version_manager.clear_pending_version()
                    self._pending_version = None
                self._state = WriteTransactionState.FAILED
                logger.info("Transaction: FAILED (publish failed, pending version rolled back)")
                if self._on_publish_failure:
                    self._on_publish_failure("Publish operation failed (push failed)")
                # Keep lock for potential retry
                return False
        except Exception as e:
            # Exception: rollback pending version
            if self._version_manager:
                self._version_manager.clear_pending_version()
                self._pending_version = None
            self._state = WriteTransactionState.FAILED
            logger.exception(f"Publish exception: {e}")
            if self._on_publish_failure:
                self._on_publish_failure(str(e))
            return False

    def _do_publish(self) -> bool:
        """Actual publish logic – use publish_only with user."""
        if self._sync_service:
            # Get user from session
            user = "system"
            session = self._collab.get_session()
            if session and session.username:
                user = session.username
            logger.info(f"Executing publish-only as user: {user}")
            return self._sync_service.publish_only(message="Finish Editing", user=user)
        logger.warning("No sync service available for publish")
        return False

    def _release_lock(self) -> None:
        """Release the write lock."""
        if self._collab.is_writing():
            self._collab.release_write()
            self._state = WriteTransactionState.IDLE
            logger.info("Transaction: IDLE (lock released)")

    def retry_publish(self) -> bool:
        """Retry publish after failure. Reuses pending version."""
        if self._state not in (WriteTransactionState.FAILED, WriteTransactionState.OFFLINE_PENDING_PUBLISH):
            logger.warning(f"Retry called in state {self._state}, ignoring")
            return False
        logger.info("Retrying publish...")
        self._state = WriteTransactionState.LOCAL_SAVED
        return self._publish()

    def continue_offline(self) -> bool:
        """Continue editing offline without publishing."""
        if self._state != WriteTransactionState.FAILED:
            logger.warning(f"Continue offline called in state {self._state}, ignoring")
            return False
        self._state = WriteTransactionState.OFFLINE_PENDING_PUBLISH
        logger.info("Transaction: OFFLINE_PENDING_PUBLISH")
        return True

    def cancel_editing(self, force: bool = False) -> bool:
        """Cancel editing with safety check."""
        if not self.is_editing:
            logger.warning(f"Cancel editing in state {self._state}, ignoring")
            return False

        if self._has_changes and not force:
            logger.warning("Cancel called with pending changes, force=False")
            return False

        # Restore snapshot if changes exist and force=True
        if force and self._has_changes:
            if not self._restore_snapshot():
                logger.error("Snapshot restore failed, lock retained")
                self._state = WriteTransactionState.FAILED
                return False

        if self._collab.is_writing():
            self._collab.release_write()
        self._state = WriteTransactionState.IDLE
        self._has_changes = False
        self._pending_version = None
        logger.info("Transaction: IDLE (cancelled)")
        return True

    def get_state_display(self) -> str:
        """Human-readable state name."""
        return self._state.name