# -*- coding: utf-8 -*-
"""PlatformLifecycle - Application lifetime management."""

from enum import Enum, auto
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class PlatformLifecycleState(Enum):
    """Platform lifecycle states."""
    CREATED = auto()
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()


@dataclass
class PlatformLifecycle:
    """Manages application lifetime."""
    
    state: PlatformLifecycleState = PlatformLifecycleState.CREATED
    previous_state: Optional[PlatformLifecycleState] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    
    def transition_to(self, new_state: PlatformLifecycleState) -> None:
        """Transition to a new state."""
        self.previous_state = self.state
        self.state = new_state
        if new_state == PlatformLifecycleState.RUNNING and self.started_at is None:
            self.started_at = datetime.now()
        if new_state == PlatformLifecycleState.STOPPED:
            self.stopped_at = datetime.now()
    
    def is_ready(self) -> bool:
        return self.state == PlatformLifecycleState.READY
    
    def is_running(self) -> bool:
        return self.state == PlatformLifecycleState.RUNNING
    
    def is_stopped(self) -> bool:
        return self.state == PlatformLifecycleState.STOPPED