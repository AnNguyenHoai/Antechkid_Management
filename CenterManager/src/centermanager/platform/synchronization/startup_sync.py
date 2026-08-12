import logging
from typing import Optional

from centermanager.platform.runtime.state import RuntimeState, RuntimeStateMachine
from centermanager.platform.deployment import RepositoryManager, RuntimeValidator
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider
from centermanager.platform.collaboration import CollaborationManager, CollaborationMode
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)

class StartupSynchronization:
    def __init__(
        self,
        repo_manager: RepositoryManager,
        validator: RuntimeValidator,
        sync_provider: Optional[GitSynchronizationProvider],
        collab_manager: CollaborationManager,
        state_machine: RuntimeStateMachine,
        notification_service: NotificationService,
    ):
        self.repo_manager = repo_manager
        self.validator = validator
        self.sync_provider = sync_provider
        self.collab_manager = collab_manager
        self.state_machine = state_machine
        self.notification_service = notification_service

    def run(self) -> bool:
        self.state_machine.transition_to(RuntimeState.SYNCHRONIZING)

        # 1. Check repository exists and valid
        if not self.repo_manager.is_deployed():
            logger.error("Repository not deployed.")
            self.state_machine.transition_to(RuntimeState.ERROR)
            return False

        if not self.validator.is_healthy():
            logger.error("Runtime unhealthy.")
            self.state_machine.transition_to(RuntimeState.RECOVERING)
            # Attempt recovery (could be implemented)
            self.state_machine.transition_to(RuntimeState.ERROR)
            return False

        # 2. If sync provider available, perform sync
        if self.sync_provider:
            try:
                # Fetch remote
                if not self.sync_provider.fetch():
                    logger.warning("Fetch failed, proceeding with local runtime.")
                    self.state_machine.transition_to(RuntimeState.OFFLINE)
                    self.notification_service.notify("Cannot connect to Git. Running offline.", "warning")
                    return True  # still usable

                # Pull if in READ mode (or if no write lock)
                if self.collab_manager.current_mode() == CollaborationMode.READ:
                    if self.sync_provider.pull():
                        logger.info("Startup pull successful.")
                    else:
                        logger.warning("Startup pull failed, using local runtime.")
                else:
                    logger.info("Write mode active, skipping pull.")
                self.state_machine.transition_to(RuntimeState.READY)
                return True

            except Exception as e:
                logger.exception("Startup sync error")
                self.state_machine.transition_to(RuntimeState.ERROR)
                return False
        else:
            # No sync configured
            self.state_machine.transition_to(RuntimeState.READY)
            return True