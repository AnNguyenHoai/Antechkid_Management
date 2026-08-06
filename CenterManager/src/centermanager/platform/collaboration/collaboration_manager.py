# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional

from centermanager.events.event_bus import EventBus
from .mode_manager import ModeManager, CollaborationMode
from .lock_manager import LockManager
from .edit_session_manager import EditSessionManager
from .metadata_repository import MetadataRepository
from .json_metadata_repository import JsonMetadataRepository
from .lock_repository import LockRepository
from .json_lock_repository import JsonLockRepository
from .metadata_initializer import MetadataInitializer
from .write_workflow import WriteWorkflow
from .release_workflow import ReleaseWorkflow
from .identity_provider import IdentityProvider
from .default_identity_provider import DefaultIdentityProvider
from .recovery_manager import RecoveryManager
from .heartbeat import HeartbeatService, HeartbeatTimer

from centermanager.platform.synchronization import SynchronizationProvider
from centermanager.platform.workflow.publish_workflow import PublishWorkflow, PublicationTransaction
from centermanager.platform.version.version_manager import VersionManager
from centermanager.platform.notification import NotificationService
from centermanager.platform.backup import BackupService
from centermanager.platform.health import CollaborationHealthChecker

import logging
logger = logging.getLogger(__name__)


class CollaborationManager:
    def __init__(
        self,
        metadata_dir: Path,
        event_bus: EventBus,
        identity_provider: Optional[IdentityProvider] = None,
        metadata_repository: Optional[MetadataRepository] = None,
        lock_repository: Optional[LockRepository] = None,
        sync_provider: Optional[SynchronizationProvider] = None,
        version_manager: Optional[VersionManager] = None,
        notification_service: Optional[NotificationService] = None,
        lock_timeout_seconds: int = 60,
        heartbeat_interval_seconds: int = 10,
        app_version: str = "0.1.0",
    ):
        self._metadata_dir = metadata_dir
        self._event_bus = event_bus
        self._app_version = app_version
        self._heartbeat_interval = heartbeat_interval_seconds

        # Setup repositories
        if metadata_repository is None:
            metadata_repository = JsonMetadataRepository(metadata_dir)
        self._metadata_repository = metadata_repository

        if lock_repository is None:
            lock_file = metadata_dir / "lock.json"
            lock_repository = JsonLockRepository(lock_file)
        self._lock_repository = lock_repository

        # Initialize metadata
        initializer = MetadataInitializer(self._metadata_repository)
        initializer.ensure_initialized()

        # Setup managers
        self._mode_manager = ModeManager()
        self._lock_manager = LockManager(self._lock_repository, timeout_seconds=lock_timeout_seconds)
        self._session_manager = EditSessionManager()

        # Identity provider
        if identity_provider is None:
            identity_provider = DefaultIdentityProvider()
        self._identity_provider = identity_provider

        # Synchronization provider (optional)
        self._sync_provider = sync_provider

        # Version manager (optional, will use metadata repo if not provided)
        if version_manager is None:
            from centermanager.platform.version.version_manager import VersionManager as VM
            version_manager = VM(self._metadata_repository, event_bus)
        self._version_manager = version_manager

        # Notification service (optional)
        if notification_service is None:
            notification_service = NotificationService()
        self._notification_service = notification_service

        # Backup service
        self._backup_service = BackupService(event_bus)

        # Heartbeat
        self._heartbeat_service = HeartbeatService(
            lock_repository=self._lock_repository,
            interval_seconds=heartbeat_interval_seconds,
            app_version=app_version,
        )
        self._heartbeat_timer = HeartbeatTimer(
            service=self._heartbeat_service,
            interval_ms=heartbeat_interval_seconds * 1000,
        )

        # Recovery manager
        self._recovery_manager = RecoveryManager(
            lock_manager=self._lock_manager,
            metadata_repository=self._metadata_repository,
            event_bus=self._event_bus,
        )
        self._lock_manager._force_release()
        # Health checker
        self._health_checker = CollaborationHealthChecker(
            lock_manager=self._lock_manager,
            metadata_repository=self._metadata_repository,
            version_manager=self._version_manager,
            sync_provider=self._sync_provider,
        )

        # Workflows
        self._write_workflow = WriteWorkflow(
            self._lock_manager,
            self._session_manager,
            self._mode_manager,
            self._identity_provider,
            self._event_bus,
        )
        self._release_workflow = ReleaseWorkflow(
            self._lock_manager,
            self._session_manager,
            self._mode_manager,
            self._identity_provider,
            self._event_bus,
        )
        self._publish_workflow = PublishWorkflow(
            lock_manager=self._lock_manager,
            mode_manager=self._mode_manager,
            session_manager=self._session_manager,
            sync_provider=self._sync_provider,
            version_manager=self._version_manager,
            event_bus=self._event_bus,
            notification_service=self._notification_service,
            backup_service=self._backup_service,
        )

        # Run recovery on startup
        self._run_startup_recovery()

    def _run_startup_recovery(self) -> None:
        """Run recovery inspection and repair on startup."""
        logger.info("CollaborationManager: running startup recovery")
        report = self._recovery_manager.inspect_and_recover()
        if report.get("recovered", False):
            logger.info(f"Recovery performed: {report}")
        else:
            logger.info("No recovery needed")

    def current_mode(self) -> CollaborationMode:
        return self._mode_manager.current_mode()

    def request_write(self) -> bool:
        # ----- XỬ LÝ GIT (cho phép write dù có lỗi) -----
        if self._sync_provider:
            try:
                if self._sync_provider.is_offline():
                    self._notification_service.notify("Git repository offline. Write mode may not synchronize.", "warning")
                    logger.warning("Git is offline, but allowing write anyway.")
                else:
                    if not self._sync_provider.fetch():
                        self._notification_service.notify("Git fetch failed. Write mode may not synchronize.", "warning")
                        logger.warning("Git fetch failed, but continuing.")
                    if not self._sync_provider.pull():
                        self._notification_service.notify("Git pull failed. Write mode may not synchronize.", "warning")
                        logger.warning("Git pull failed, but continuing.")
            except Exception as e:
                logger.exception(f"Git sync error: {e}, but allowing write.")
                self._notification_service.notify(f"Git error: {e}. Write mode may not synchronize.", "warning")

        # FIX: Thực sự yêu cầu quyền ghi và trả về kết quả
        return self._write_workflow.execute()

    def release_write(self) -> bool:
        # Stop heartbeat
        self._heartbeat_timer.stop()
        self._heartbeat_service.stop()
        return self._release_workflow.execute()

    def publish(self, message: str = "Publish") -> bool:
        """Publish changes (commit + push) and switch to READ."""
        if not self._sync_provider:
            return False
        return self._publish_workflow.execute(message=message)

    def get_version(self) -> int:
        version_data = self._metadata_repository.load_version()
        return version_data.get("platform_version", 1)

    def get_deployment_profile(self) -> str:
        deployment_data = self._metadata_repository.load_deployment()
        return deployment_data.get("profile", "Standalone")

    def get_session_info(self) -> dict:
        return {
            "session_id": self._session_manager.get_session_id(),
            "owner": self._session_manager.get_owner(),
            "active": self._session_manager.is_active(),
        }

    def ensure_write(self) -> bool:
        return self.current_mode() == CollaborationMode.WRITE

    def synchronization_status(self) -> dict:
        """Return synchronization status if provider exists."""
        if self._sync_provider:
            return self._sync_provider.status()
        return {"state": "disabled"}

    def get_health(self):
        """Get collaboration health status."""
        return self._health_checker.check_all()

    def get_recovery_report(self):
        """Get last recovery report."""
        # We could store the last report, but for simplicity, run a new inspection
        return self._recovery_manager.inspect_and_recover()

    def get_diagnostics(self) -> dict:
        """Get full diagnostics for collaboration status."""
        lock = self._lock_repository.get_lock()
        version_data = self._metadata_repository.load_version()
        deployment_data = self._metadata_repository.load_deployment()
        sync_status = self._sync_provider.status() if self._sync_provider else {"state": "disabled"}

        return {
            "mode": self._mode_manager.current_mode().value if self._mode_manager.current_mode() else "UNKNOWN",
            "user": self._identity_provider.current_user_id(),
            "platform_version": version_data.get("platform_version", 0),
            "deployment_profile": deployment_data.get("profile", "Standalone"),
            "lock": {
                "locked": lock.get("locked", False),
                "owner": lock.get("owner"),
                "session_id": lock.get("session_id"),
                "started_at": lock.get("started_at"),
                "last_heartbeat": lock.get("last_heartbeat"),
                "heartbeat_version": lock.get("heartbeat_version"),
                "is_stale": self._lock_manager.is_stale(),
            },
            "session": self.get_session_info(),
            "git": sync_status,
            "heartbeat": self._heartbeat_service.get_status(),
        }