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

# Import synchronization and workflow
from centermanager.platform.synchronization import SynchronizationProvider
from centermanager.platform.workflow.publish_workflow import PublishWorkflow
from centermanager.platform.version.version_manager import VersionManager
from centermanager.platform.notification import NotificationService


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
    ):
        self._metadata_dir = metadata_dir
        self._event_bus = event_bus

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
        self._lock_manager = LockManager(self._lock_repository)
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
        )

    def current_mode(self) -> CollaborationMode:
        return self._mode_manager.current_mode()

    def request_write(self) -> bool:
        # If we have sync provider, fetch/pull before acquiring lock
        if self._sync_provider:
            self._sync_provider.fetch()
            if not self._sync_provider.pull():
                return False
        return self._write_workflow.execute()

    def release_write(self) -> bool:
        return self._release_workflow.execute()

    def publish(self, message: str = "Publish") -> bool:
        """Publish changes (commit + push) and switch to READ.
        
        Args:
            message: Commit message for the publish.
        """
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