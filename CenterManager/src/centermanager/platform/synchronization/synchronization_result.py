# -*- coding: utf-8 -*-
"""SynchronizationResult - Result of synchronization operation."""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Any


class SyncResult(Enum):
    """Possible results of synchronization operations."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NO_CHANGE = "no_change"
    OFFLINE = "offline"
    CONFLICT = "conflict"


@dataclass
class SynchronizationResult:
    """Result of a synchronization operation."""
    
    result: SyncResult
    message: str = ""
    provider: Optional[str] = None
    current_version: Optional[int] = None
    remote_version: Optional[int] = None
    duration_ms: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    details: Any = None
    
    def is_success(self) -> bool:
        return self.result == SyncResult.SUCCESS
    
    def is_failed(self) -> bool:
        return self.result == SyncResult.FAILED
    
    def is_cancelled(self) -> bool:
        return self.result == SyncResult.CANCELLED
    
    def has_change(self) -> bool:
        return self.result in (SyncResult.SUCCESS, SyncResult.CONFLICT)