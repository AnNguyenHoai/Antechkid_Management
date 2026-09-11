# -*- coding: utf-8 -*-
from .lock_manager import LockManager
from .edit_session_manager import EditSessionManager
from .mode_manager import ModeManager, CollaborationMode
from .identity_provider import IdentityProvider
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import WriteReleased, ModeChanged
import logging

logger = logging.getLogger(__name__)


class ReleaseWorkflow:
    def __init__(self, lock_manager: LockManager, session_manager: EditSessionManager,
                 mode_manager: ModeManager, identity_provider: IdentityProvider,
                 event_bus: EventBus):
        self._lock_manager = lock_manager
        self._session_manager = session_manager
        self._mode_manager = mode_manager
        self._identity_provider = identity_provider
        self._event_bus = event_bus

    def execute(self) -> bool:
        if self._mode_manager.current_mode() != CollaborationMode.WRITE:
            return False

        current_user = self._identity_provider.current_user()
        if current_user is None:
            return False

        owner = self._identity_provider.current_user_id()
        if owner is None:
            return False

        # Release lock, catch any exception
        try:
            if not self._lock_manager.release(owner):
                logger.error("Failed to release lock.")
                return False
        except Exception as e:
            logger.exception(f"Exception while releasing lock: {e}")
            return False

        self._session_manager.end_session()
        self._mode_manager.set_mode(CollaborationMode.READ)
        self._event_bus.publish(WriteReleased(owner=owner))
        self._event_bus.publish(ModeChanged(mode=CollaborationMode.READ))
        return True