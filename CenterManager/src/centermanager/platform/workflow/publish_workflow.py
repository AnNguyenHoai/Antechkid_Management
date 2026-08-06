# -*- coding: utf-8 -*-
"""
Publish workflow - commits and pushes changes to synchronization backend.
"""
import logging
from datetime import datetime
from typing import Optional

from centermanager.platform.collaboration.mode_manager import ModeManager, CollaborationMode
from centermanager.platform.collaboration.lock_manager import LockManager
from centermanager.platform.collaboration.edit_session_manager import EditSessionManager
from centermanager.platform.synchronization import SynchronizationProvider
from centermanager.platform.version.version_manager import VersionManager
from centermanager.events.event_bus import EventBus
from centermanager.platform.notification import NotificationService
from centermanager.events.synchronization_events import (
    PublishStarted, PublishSucceeded, PublishFailed,
    SynchronizationStarted, SynchronizationCompleted, SynchronizationFailed,
    VersionUpdated
)
from centermanager.events.collaboration_events import ModeChanged
logger = logging.getLogger(__name__)


class PublishWorkflow:
    def __init__(
        self,
        lock_manager: LockManager,
        mode_manager: ModeManager,
        session_manager: EditSessionManager,
        sync_provider: SynchronizationProvider,
        version_manager: VersionManager,
        event_bus: EventBus,
        notification_service: NotificationService,
    ):
        self._lock_manager = lock_manager
        self._mode_manager = mode_manager
        self._session_manager = session_manager
        self._sync_provider = sync_provider
        self._version_manager = version_manager
        self._event_bus = event_bus
        self._notification_service = notification_service

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

        logger.info(f"Publishing: session={session_id}, owner={owner}, message='{message}'")

        self._event_bus.publish(PublishStarted(session_id=session_id))
        self._notification_service.notify("Publishing changes...", "info")

        try:
            # Step 1: Synchronize
            self._event_bus.publish(SynchronizationStarted(session_id=session_id))
            logger.info("Calling sync_provider.publish()...")
            success = self._sync_provider.publish(message=message, user=owner)
            logger.info(f"sync_provider.publish() returned {success}")
            if not success:
                self._event_bus.publish(SynchronizationFailed(session_id=session_id))
                self._event_bus.publish(PublishFailed(session_id=session_id))
                self._notification_service.notify("Publish failed.", "error")
                return False
            self._event_bus.publish(SynchronizationCompleted(session_id=session_id))

            # Step 2: Increment version
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

            # Step 3: Release lock and switch to READ
            lock_released = False
            try:
                logger.debug("Checking lock status before release...")
                if self._lock_manager.is_locked():
                    logger.debug(f"Lock is currently locked, releasing by owner={owner}")
                    lock_released = self._lock_manager.release(owner)
                    logger.debug(f"Lock release result: {lock_released}")
                else:
                    logger.info("Lock is not locked, skipping release.")
                    lock_released = True
            except Exception as e:
                logger.exception(f"Exception while releasing lock: {e}")
                lock_released = False

            # Always end session and switch to READ mode
            self._session_manager.end_session()
            self._mode_manager.set_mode(CollaborationMode.READ)
            logger.info("Session ended, mode switched to READ.")
            self._event_bus.publish(ModeChanged(mode=CollaborationMode.READ))
            # Step 4: Notify and events
            self._event_bus.publish(PublishSucceeded(session_id=session_id, version=new_version))
            if lock_released:
                self._notification_service.notify(f"Publish succeeded. Version {new_version}", "success")
                logger.info(f"Publish succeeded with lock release. Version {new_version}")
            else:
                self._notification_service.notify(
                    f"Publish succeeded but lock could not be released. Version {new_version}",
                    "warning"
                )
                logger.warning(f"Publish succeeded but lock release failed. Version {new_version}")

            return True

        except Exception as e:
            logger.exception("Publish workflow failed with exception")
            self._event_bus.publish(SynchronizationFailed(session_id=session_id))
            self._event_bus.publish(PublishFailed(session_id=session_id))
            self._notification_service.notify(f"Publish error: {str(e)}", "error")
            return False