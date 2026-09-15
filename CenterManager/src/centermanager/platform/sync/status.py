# -*- coding: utf-8 -*-
"""Runtime synchronization status."""

from enum import Enum


class SyncStatus(Enum):
    """Status of Runtime synchronization."""
    IDLE = "idle"
    CHECKING = "checking"
    SYNC_PENDING = "sync_pending"
    SYNCHRONIZING = "synchronizing"
    WAITING = "waiting"
    FAILED = "failed"

    def is_active(self) -> bool:
        """Check if synchronization is actively running."""
        return self in (self.SYNCHRONIZING, self.CHECKING)

    def is_pending(self) -> bool:
        """Check if sync is pending."""
        return self == self.SYNC_PENDING

    def has_failed(self) -> bool:
        """Check if sync has failed."""
        return self == self.FAILED
    