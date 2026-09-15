import logging
import threading
import time
from typing import Optional

from centermanager.platform.runtime.state import RuntimeState, RuntimeStateMachine
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider
from centermanager.platform.collaboration import CollaborationManager, CollaborationMode
from centermanager.platform.notification import NotificationService
from centermanager.events.collaboration_events import WriteReleased, ModeChanged
from centermanager.events.event_bus import EventBus
from centermanager.events.synchronization_events import VersionUpdated

logger = logging.getLogger(__name__)

class BackgroundSync:
    def __init__(
        self,
        sync_provider: Optional[GitSynchronizationProvider],
        collab_manager: CollaborationManager,
        state_machine: RuntimeStateMachine,
        event_bus: EventBus,
        notification_service: NotificationService,
        poll_interval: int = 30,
    ):
        self.sync_provider = sync_provider
        self.collab_manager = collab_manager
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.notification_service = notification_service
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._background_loop, daemon=True)
        self._thread.start()
        # Subscribe to events
        self.event_bus.register(WriteReleased, self._on_write_released)
        self.event_bus.register(ModeChanged, self._on_mode_changed)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _background_loop(self):
        while self._running:
            time.sleep(self.poll_interval)
            self._check_and_sync()

    def _check_and_sync(self):
        if not self.sync_provider:
            return
        current_state = self.state_machine.state
        if current_state not in (RuntimeState.READY, RuntimeState.OFFLINE):
            return
        if self.collab_manager.current_mode() != CollaborationMode.READ:
            return

        try:
            # Fetch remote
            if self.sync_provider.fetch():
                # We could check if remote is newer, but simple pull is okay.
                if self.sync_provider.pull():
                    logger.info("Background sync: pull succeeded.")
                    self._reload_runtime()
                else:
                    # No changes or error
                    pass
        except Exception as e:
            logger.exception("Background sync error")

    def _on_write_released(self, event: WriteReleased):
        # Immediately check for updates after write release
        self._check_and_sync()

    def _on_mode_changed(self, event: ModeChanged):
        if event.mode == CollaborationMode.READ:
            self._check_and_sync()

    def _reload_runtime(self):
        # Notify UI to refresh
        self.notification_service.notify("New runtime version available. Refreshing...", "info")
        self.event_bus.publish(VersionUpdated(old_version=None, new_version=None))