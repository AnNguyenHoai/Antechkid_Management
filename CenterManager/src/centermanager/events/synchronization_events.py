from .event import Event
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SynchronizationStarted(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SynchronizationCompleted(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SynchronizationFailed(Event):
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishStarted(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishSucceeded(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PublishFailed(Event):
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class VersionUpdated(Event):
    version: int
    timestamp: datetime = field(default_factory=datetime.now)