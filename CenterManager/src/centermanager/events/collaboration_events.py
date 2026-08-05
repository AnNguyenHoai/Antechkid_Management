from .event import Event
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class WriteRequested(Event):
    timestamp: datetime = field(default_factory=datetime.now)
    user: Optional[str] = None
    session_id: Optional[str] = None

@dataclass
class WriteGranted(Event):
    session_id: str
    owner: str
    timestamp: datetime = field(default_factory=datetime.now)
    platform_version: Optional[int] = None

@dataclass
class WriteReleased(Event):
    owner: str
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: Optional[str] = None

@dataclass
class ModeChanged(Event):
    mode: str  # CollaborationMode value (READ/WRITE)
    timestamp: datetime = field(default_factory=datetime.now)
    old_mode: Optional[str] = None
    user: Optional[str] = None
    session_id: Optional[str] = None