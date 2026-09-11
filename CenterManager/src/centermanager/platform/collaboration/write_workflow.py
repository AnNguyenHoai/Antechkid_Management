from .lock_manager import LockManager
from .edit_session_manager import EditSessionManager
from .mode_manager import ModeManager, CollaborationMode
from .identity_provider import IdentityProvider
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import WriteRequested, WriteGranted, ModeChanged
import logging
logger = logging.getLogger(__name__)
class WriteWorkflow:
    def __init__(self, lock_manager: LockManager, session_manager: EditSessionManager,
                 mode_manager: ModeManager, identity_provider: IdentityProvider,
                 event_bus: EventBus):
        self._lock_manager = lock_manager
        self._session_manager = session_manager
        self._mode_manager = mode_manager
        self._identity_provider = identity_provider
        self._event_bus = event_bus

    # src/centermanager/platform/collaboration/write_workflow.py

    def execute(self) -> bool:
        self._event_bus.publish(WriteRequested())
        if self._mode_manager.current_mode() == CollaborationMode.WRITE:
            return True
        current_user = self._identity_provider.current_user()
        if current_user is None:
            logger.warning("WriteWorkflow: current_user is None")
            return False
        owner = self._identity_provider.current_user_id()
        if owner is None:
            logger.warning("WriteWorkflow: owner is None")
            return False
        if self._lock_manager.is_locked():
            existing_owner = self._lock_manager.get_owner()
            logger.info(f"WriteWorkflow: lock is locked, existing_owner={existing_owner}, current_owner={owner}")
            if existing_owner != owner:
                logger.warning("WriteWorkflow: lock owner mismatch, denying write")
                return False
            if not self._session_manager.is_active():
                self._session_manager.start_session(owner)
            self._mode_manager.set_mode(CollaborationMode.WRITE)
            self._event_bus.publish(WriteGranted(session_id=self._session_manager.get_session_id(), owner=owner))
            self._event_bus.publish(ModeChanged(mode=CollaborationMode.WRITE))
            return True
        session_id = self._session_manager.start_session(owner)
        if not self._lock_manager.acquire(owner, session_id):
            logger.warning("WriteWorkflow: lock acquisition failed")
            self._session_manager.end_session()
            return False
        self._mode_manager.set_mode(CollaborationMode.WRITE)
        self._event_bus.publish(WriteGranted(session_id=session_id, owner=owner))
        self._event_bus.publish(ModeChanged(mode=CollaborationMode.WRITE))
        return True