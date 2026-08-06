from .event import Event
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SynchronizationStarted(Event):
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SynchronizationCompleted(Event):
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SynchronizationFailed(Event):
    session_id: Optional[str] = None
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishStarted(Event):
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishSucceeded(Event):
    session_id: Optional[str] = None
    version: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishFailed(Event):
    session_id: Optional[str] = None
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class VersionUpdated(Event):
    old_version: Optional[int] = None
    new_version: Optional[int] = None
    session_id: Optional[str] = None
    user: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)