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

class CollaborationManager:
    def __init__(
        self,
        metadata_dir: Path,
        event_bus: EventBus,
        identity_provider: Optional[IdentityProvider] = None,
        metadata_repository: Optional[MetadataRepository] = None,
        lock_repository: Optional[LockRepository] = None,
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

    def current_mode(self) -> CollaborationMode:
        return self._mode_manager.current_mode()

    def request_write(self) -> bool:
        return self._write_workflow.execute()

    def release_write(self) -> bool:
        return self._release_workflow.execute()

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