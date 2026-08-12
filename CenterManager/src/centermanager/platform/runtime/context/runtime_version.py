# -*- coding: utf-8 -*-
"""RuntimeVersion - Version tracking."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeVersion:
    """Runtime version information."""
    
    current: int = 0
    desired: Optional[int] = None
    last_pull: Optional[datetime] = None
    last_publish: Optional[datetime] = None
    
    def is_outdated(self) -> bool:
        """Check if current version is behind desired."""
        if self.desired is None:
            return False
        return self.current < self.desired
    
    def update_current(self, version: int) -> None:
        """Update current version."""
        self.current = version
        self.last_pull = datetime.now()
    
    def update_desired(self, version: int) -> None:
        """Update desired version."""
        self.desired = version
    
    def mark_published(self, version: int) -> None:
        """Mark that a version was published."""
        self.current = version
        self.desired = version
        self.last_publish = datetime.now()