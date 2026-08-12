# -*- coding: utf-8 -*-
"""ReloadDecisionService - Decides if reload is safe."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class ReloadDecision(Enum):
    """Possible reload decisions."""
    RELOAD_NOW = "reload_now"
    WAIT = "wait"
    RESTART_REQUIRED = "restart_required"
    SKIP = "skip"


@dataclass
class ReloadState:
    """State for reload decision."""
    has_dirty_workspace: bool = False
    has_unsaved_changes: bool = False
    has_open_dialog: bool = False
    has_background_task: bool = False
    is_writing: bool = False
    has_pending_queue: bool = False


class ReloadDecisionService:
    """Service to decide if reload is safe."""

    def decide(self, state: ReloadState) -> ReloadDecision:
        """Make reload decision based on current state."""
        # Critical conditions - must wait
        if state.has_unsaved_changes:
            return ReloadDecision.WAIT

        if state.is_writing:
            return ReloadDecision.WAIT

        if state.has_open_dialog:
            return ReloadDecision.WAIT

        if state.has_dirty_workspace:
            return ReloadDecision.WAIT

        if state.has_background_task:
            return ReloadDecision.WAIT

        # Can reload now
        return ReloadDecision.RELOAD_NOW

    def is_safe(self, state: ReloadState) -> bool:
        """Check if reload is safe."""
        return self.decide(state) == ReloadDecision.RELOAD_NOW