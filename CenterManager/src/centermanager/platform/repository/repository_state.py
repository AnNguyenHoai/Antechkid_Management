# -*- coding: utf-8 -*-
"""RepositoryState - Runtime repository state."""

from enum import Enum


class RepositoryState(Enum):
    """State of the Runtime Repository."""

    NOT_FOUND = "not_found"
    READY = "ready"
    INVALID = "invalid"
    CORRUPTED = "corrupted"
    OFFLINE = "offline"

    def is_operational(self) -> bool:
        """Check if repository is operational (READY)."""
        return self == RepositoryState.READY

    def needs_recovery(self) -> bool:
        """Check if repository needs recovery."""
        return self in (RepositoryState.INVALID, RepositoryState.CORRUPTED)