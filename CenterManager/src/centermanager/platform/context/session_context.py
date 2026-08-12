# -*- coding: utf-8 -*-
"""SessionContext - User session information."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class SessionContext:
    """Current user session."""
    
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    authenticated: bool = False
    started_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    mode: str = "READ"  # READ, WRITE
    
    def is_active(self, timeout_seconds: int = 120) -> bool:
        if self.last_heartbeat is None:
            return False
        return (datetime.now() - self.last_heartbeat).total_seconds() < timeout_seconds
    
    def update_heartbeat(self) -> None:
        self.last_heartbeat = datetime.now()