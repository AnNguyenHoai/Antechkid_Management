# -*- coding: utf-8 -*-
"""RuntimeSession - Session information for collaboration."""

import uuid
import platform
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class RuntimeSession:
    """Represents a running application session."""
    
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    machine_fingerprint: str = field(default_factory=lambda: platform.node())
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    last_heartbeat: datetime = field(default_factory=datetime.now)
    runtime_version: int = 0
    capabilities: List[str] = field(default_factory=list)
    is_active: bool = True
    
    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        self.last_heartbeat = datetime.now()
    
    def is_expired(self, timeout_seconds: int = 30) -> bool:
        """Check if session has expired due to heartbeat timeout."""
        elapsed = (datetime.now() - self.last_heartbeat).total_seconds()
        return elapsed > timeout_seconds
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "machine_fingerprint": self.machine_fingerprint,
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role,
            "started_at": self.started_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "runtime_version": self.runtime_version,
            "capabilities": self.capabilities,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeSession":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            machine_fingerprint=data.get("machine_fingerprint", platform.node()),
            user_id=data.get("user_id"),
            username=data.get("username"),
            role=data.get("role"),
            started_at=datetime.fromisoformat(data["started_at"]),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            runtime_version=data.get("runtime_version", 0),
            capabilities=data.get("capabilities", []),
            is_active=data.get("is_active", True),
        )