# -*- coding: utf-8 -*-
"""RuntimeState - Platform runtime state machine."""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class RuntimeState(Enum):
    """Platform runtime states."""
    
    BOOTSTRAP = auto()           # Application starting
    INITIALIZING = auto()        # Initializing components
    CHECK_REPOSITORY = auto()    # Checking repository existence
    VALIDATING = auto()          # Validating runtime
    READY = auto()               # Platform ready
    OFFLINE = auto()             # Offline mode
    ERROR = auto()               # Error state


@dataclass
class RuntimeStateMachine:
    """Manages runtime state transitions with history."""
    
    current: RuntimeState = RuntimeState.BOOTSTRAP
    previous: Optional[RuntimeState] = None
    changed_at: datetime = field(default_factory=datetime.now)
    
    def transition_to(self, new_state: RuntimeState) -> None:
        """Transition to a new state."""
        self.previous = self.current
        self.current = new_state
        self.changed_at = datetime.now()
    
    def is_ready(self) -> bool:
        """Check if platform is ready."""
        return self.current == RuntimeState.READY
    
    def is_error(self) -> bool:
        """Check if platform is in error state."""
        return self.current == RuntimeState.ERROR
    
    def is_offline(self) -> bool:
        """Check if platform is offline."""
        return self.current == RuntimeState.OFFLINE