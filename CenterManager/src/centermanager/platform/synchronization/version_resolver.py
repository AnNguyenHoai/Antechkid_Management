# -*- coding: utf-8 -*-
"""VersionResolver - Compare runtime versions."""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class VersionStatus(Enum):
    """Status of version comparison."""
    UP_TO_DATE = "up_to_date"
    OUTDATED = "outdated"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


@dataclass
class VersionResolver:
    """Resolve version differences."""
    
    def resolve(self, current: int, remote: Optional[int]) -> VersionStatus:
        """
        Compare current and remote versions.
        Returns version status.
        """
        if remote is None:
            return VersionStatus.UNKNOWN
        if current < remote:
            return VersionStatus.OUTDATED
        if current > remote:
            return VersionStatus.CONFLICT
        return VersionStatus.UP_TO_DATE
    
    def needs_sync(self, current: int, remote: Optional[int]) -> bool:
        """Check if synchronization is needed."""
        status = self.resolve(current, remote)
        return status in (VersionStatus.OUTDATED, VersionStatus.UNKNOWN)
    
    def is_conflict(self, current: int, remote: Optional[int]) -> bool:
        """Check if versions are in conflict."""
        return self.resolve(current, remote) == VersionStatus.CONFLICT