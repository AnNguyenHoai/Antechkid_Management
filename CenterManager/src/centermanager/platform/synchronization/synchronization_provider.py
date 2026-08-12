# -*- coding: utf-8 -*-
"""SynchronizationProvider - Interface for sync backends."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class SynchronizationProvider(ABC):
    """Abstract interface for synchronization backends."""
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to remote."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from remote."""
        pass
    
    @abstractmethod
    def fetch(self) -> bool:
        """Fetch remote metadata without merging."""
        pass
    
    @abstractmethod
    def pull(self) -> bool:
        """Pull remote changes and merge."""
        pass
    
    @abstractmethod
    def publish(self, message: str, user: str) -> bool:
        """Publish local changes to remote."""
        pass
    
    @abstractmethod
    def status(self) -> Dict[str, Any]:
        """Return provider status."""
        pass
    
    @abstractmethod
    def remote_manifest(self) -> Optional[Dict[str, Any]]:
        """Get remote manifest without merging."""
        pass
    
    @abstractmethod
    def health(self) -> bool:
        """Check provider health."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass
    
    @abstractmethod
    def is_offline(self) -> bool:
        """Check if provider is offline."""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate provider configuration."""
        pass