# -*- coding: utf-8 -*-
"""SynchronizationBoundary - Defines synchronization contract."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    
    success: bool
    message: str = ""
    version: Optional[int] = None
    data: Optional[Dict[str, Any]] = None


class PersistenceProvider(ABC):
    """Abstract persistence provider for synchronization."""
    
    @abstractmethod
    def get_current_state(self) -> Dict[str, Any]:
        """Get current persisted state for synchronization."""
        pass
    
    @abstractmethod
    def apply_state(self, state: Dict[str, Any]) -> bool:
        """Apply new state from synchronization."""
        pass
    
    @abstractmethod
    def get_version(self) -> int:
        """Get current version from persistence."""
        pass


class SynchronizationProvider(ABC):
    """Abstract synchronization provider - persistence-agnostic."""
    
    @abstractmethod
    def pull(self, persistence: PersistenceProvider) -> SyncResult:
        """Pull changes from remote to local persistence."""
        pass
    
    @abstractmethod
    def push(self, persistence: PersistenceProvider) -> SyncResult:
        """Push changes from local persistence to remote."""
        pass
    
    @abstractmethod
    def fetch_version(self) -> Optional[int]:
        """Fetch remote version without pulling."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if synchronization service is available."""
        pass