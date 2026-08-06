# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, Any

class SynchronizationProvider(ABC):
    @abstractmethod
    def fetch(self) -> bool:
        """Fetch latest changes from remote."""
        pass

    @abstractmethod
    def pull(self) -> bool:
        """Pull latest changes from remote."""
        pass

    @abstractmethod
    def publish(self, message: str, user: str) -> bool:
        """Commit and push changes."""
        pass

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        """Return synchronization status."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate that synchronization is configured and working."""
        pass

    @abstractmethod
    def is_offline(self) -> bool:
        """Return True if the provider is offline or in error state."""
        pass