# -*- coding: utf-8 -*-
"""BusinessModule interface and lifecycle."""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from centermanager.platform.context import PlatformContext
from centermanager.events.event_bus import EventBus


class BusinessModuleLifecycle(Enum):
    """Lifecycle states of a business module."""
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPING = "stopping"
    STOPPED = "stopped"


class BusinessModule(ABC):
    """
    Base interface for all business modules.
    Platform owns lifecycle.
    """

    @abstractmethod
    def initialize(self, context: PlatformContext, event_bus: EventBus) -> None:
        """Initialize module with platform context."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start module operations."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop module operations."""
        pass

    @abstractmethod
    def dispose(self) -> None:
        """Release resources."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get module name."""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Get module version."""
        pass

    @abstractmethod
    def get_descriptors(self) -> list:
        """Get workspace descriptors."""
        pass

    def get_lifecycle(self) -> BusinessModuleLifecycle:
        """Get current lifecycle state."""
        return getattr(self, "_lifecycle", BusinessModuleLifecycle.UNINITIALIZED)

    def _set_lifecycle(self, state: BusinessModuleLifecycle) -> None:
        """Set lifecycle state."""
        self._lifecycle = state