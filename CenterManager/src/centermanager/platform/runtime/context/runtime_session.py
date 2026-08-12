# -*- coding: utf-8 -*-
"""RuntimeSession - User session information."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class RuntimeSession:
    """Runtime session - user context."""
    
    session_id: str
    user_id: str
    username: str
    role: str
    machine_id: str
    started_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    capabilities: List[str] = field(default_factory=list)
    mode: str = "READ"  # READ, WRITE
    
    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        self.last_heartbeat = datetime.now()
    
    def is_active(self, timeout_seconds: int = 120) -> bool:
        """Check if session is still active."""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed < timeout_seconds