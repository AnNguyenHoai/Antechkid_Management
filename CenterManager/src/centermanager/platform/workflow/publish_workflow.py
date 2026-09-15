# -*- coding: utf-8 -*-
"""
Publish workflow - commits and pushes changes to synchronization backend.
Now with backup, retry, and transaction support.
"""
import logging
from datetime import datetime
from typing import Optional

from centermanager.platform.collaboration.mode_manager import ModeManager, CollaborationMode
from centermanager.platform.collaboration.lock_manager import LockManager
from centermanager.platform.collaboration.edit_session_manager import EditSessionManager
from centermanager.platform.synchronization import SynchronizationProvider
from centermanager.platform.version.version_manager import VersionManager
from centermanager.platform.backup import BackupService
from centermanager.platform.retry import RetryPolicy
from centermanager.events.event_bus import EventBus
from centermanager.platform.notification import NotificationService
from centermanager.events.synchronization_events import (
    PublishStarted, PublishSucceeded, PublishFailed,
    SynchronizationStarted, SynchronizationCompleted, SynchronizationFailed,
    VersionUpdated
)
from centermanager.events.collaboration_events import ModeChanged, BackupCreated, BackupFailed
from centermanager.events.collaboration_events import RecoveryStarted, RecoveryCompleted, RecoveryFailed

logger = logging.getLogger(__name__)


class PublicationTransaction:
    """Manages the entire publish transaction with rollback capability."""

    def __init__(
        self,
        lock_manager: LockManager,
        mode_manager: ModeManager,
        session_manager: EditSessionManager,
        sync_provider: SynchronizationProvider,
        version_manager: VersionManager,
        event_bus: EventBus,
        notification_service: NotificationService,
        backup_service: BackupService,
    ):
        self._lock_manager = lock_manager
        self._mode_manager = mode_manager
        self._session_manager = session_manager
        self._sync_provider = sync_provider
        self._version_manager = version_manager
        self._event_bus = event_bus
        self._notification_service = notification_service
        self._backup_service = backup_service
        self._backup_path = None
        self._committed = False

    def begin(self) -> bool:
        """Begin transaction. Returns True if successful."""
        if self._mode_manager.current_mode() != CollaborationMode.WRITE:
            logger.warning("Publish called in READ mode, ignoring.")
            return False

        session_id = self._session_manager.get_session_id()
        owner = self._session_manager.get_owner()
        if not session_id or not owner:
            logger.error("No active session to publish.")
            return False

        logger.info(f"PublicationTransaction begin: session={session_id}, owner={owner}")

        # 1. Create backup
        self._event_bus.publish(BackupCreated(label="pre_publish", backup_path=""))
        backup_result = self._backup_service.create_backup("pre_publish")
        if not backup_result.success:
            self._event_bus.publish(BackupFailed(error=backup_result.error or "Unknown backup error"))
            self._notification_service.notify("Backup failed. Publish aborted.", "error")
            logger.error("Backup failed, aborting publish")
            return False

        self._backup_path = backup_result.backup_path
        logger.info(f"Backup created at {self._backup_path}")
        return True

    def commit(self, message: str, user: str) -> bool:
        """Commit the transaction."""
        if self._backup_path is None:
            logger.error("Cannot commit: transaction not begun")
            return False

        session_id = self._session_manager.get_session_id()
        owner = self._session_manager.get_owner()

        try:
            # 2. Sync with retry
            self._event_bus.publish(SynchronizationStarted(session_id=session_id))
            retry_policy = RetryPolicy(max_retries=3, base_delay=1.0)
            success = retry_policy.execute(
                self._sync_provider.publish,
                message=message,
                user=user
            )

            if not success:
                self._event_bus.publish(SynchronizationFailed(session_id=session_id))
                self._notification_service.notify("Synchronization failed.", "error")
                logger.error("Synchronization failed, rolling back")
                self.rollback()
                return False

            self._event_bus.publish(SynchronizationCompleted(session_id=session_id))

            # 3. Increment version
            old_version = self._version_manager.get_current_version()
            new_version = self._version_manager.increment_version(
                metadata={
                    "session_id": session_id,
                    "owner": owner,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            logger.info(f"Version incremented: {old_version} -> {new_version}")
            self._event_bus.publish(VersionUpdated(
                old_version=old_version,
                new_version=new_version,
                session_id=session_id,
                user=owner,
            ))

            # 4. Release lock and switch to READ
            self._release_lock_and_mode(owner, session_id)

            # 5. Mark committed
            self._committed = True

            # 6. Publish success event
            self._event_bus.publish(PublishSucceeded(session_id=session_id, version=new_version))
            self._notification_service.notify(f"Publish succeeded. Version {new_version}", "success")
            logger.info(f"Publish succeeded. Version {new_version}")
            return True

        except Exception as e:
            logger.exception("Publish transaction failed")
            self._event_bus.publish(SynchronizationFailed(session_id=session_id))
            self._event_bus.publish(PublishFailed(session_id=session_id))
            self._notification_service.notify(f"Publish error: {str(e)}", "error")
            self.rollback()
            return False

    def rollback(self) -> None:
        """Rollback the transaction."""
        if self._committed:
            logger.warning("Cannot rollback: transaction already committed")
            return

        if self._backup_path and self._backup_path.exists():
            try:
                logger.info(f"Rolling back to backup: {self._backup_path}")
                self._backup_service.restore_backup(self._backup_path)
                self._notification_service.notify("Rolled back to last backup.", "warning")
            except Exception as e:
                logger.exception("Rollback restore failed")
                self._notification_service.notify(f"Rollback failed: {e}", "error")

        # Ensure lock is released even if restore fails
        owner = self._session_manager.get_owner()
        if owner:
            self._release_lock_and_mode(owner, self._session_manager.get_session_id())

        self._committed = False

    def _release_lock_and_mode(self, owner: str, session_id: Optional[str]) -> None:
        """Release lock and switch to READ mode."""
        try:
            self._lock_manager.release(owner)
        except Exception as e:
            logger.exception(f"Lock release failed: {e}")
        self._session_manager.end_session()
        self._mode_manager.set_mode(CollaborationMode.READ)
        self._event_bus.publish(ModeChanged(mode=CollaborationMode.READ))


class PublishWorkflow:
    """Legacy wrapper around PublicationTransaction for backward compatibility."""

    def __init__(
        self,
        lock_manager: LockManager,
        mode_manager: ModeManager,
        session_manager: EditSessionManager,
        sync_provider: SynchronizationProvider,
        version_manager: VersionManager,
        event_bus: EventBus,
        notification_service: NotificationService,
        backup_service: Optional[BackupService] = None,
    ):
        self._lock_manager = lock_manager
        self._mode_manager = mode_manager
        self._session_manager = session_manager
        self._sync_provider = sync_provider
        self._version_manager = version_manager
        self._event_bus = event_bus
        self._notification_service = notification_service
        self._backup_service = backup_service or BackupService(event_bus)

    def execute(self, message: str = "Publish") -> bool:
        logger.info("Publish workflow started.")

        if self._mode_manager.current_mode() != CollaborationMode.WRITE:
            logger.warning("Publish called in READ mode, ignoring.")
            return False

        session_id = self._session_manager.get_session_id()
        owner = self._session_manager.get_owner()
        if not session_id or not owner:
            logger.error("No active session to publish.")
            return False

        self._event_bus.publish(PublishStarted(session_id=session_id))
        self._notification_service.notify("Publishing changes...", "info")

        # Use PublicationTransaction
        tx = PublicationTransaction(
            lock_manager=self._lock_manager,
            mode_manager=self._mode_manager,
            session_manager=self._session_manager,
            sync_provider=self._sync_provider,
            version_manager=self._version_manager,
            event_bus=self._event_bus,
            notification_service=self._notification_service,
            backup_service=self._backup_service,
        )

        if not tx.begin():
            self._event_bus.publish(PublishFailed(session_id=session_id))
            self._notification_service.notify("Publish failed: backup error", "error")
            return False

        success = tx.commit(message, owner)
        return success