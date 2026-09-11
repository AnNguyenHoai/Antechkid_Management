# -*- coding: utf-8 -*-
"""Collaboration events for Runtime EventBus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from centermanager.events.event import Event


@dataclass
class SessionStarted(Event):
    """Event when a new session starts."""
    session_id: str
    user_id: str
    username: str
    machine_fingerprint: str
    runtime_version: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SessionEnded(Event):
    """Event when a session ends."""
    session_id: str
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WriteRequested(Event):
    """Event when a write request is enqueued."""
    request_id: str
    session_id: str
    user_id: str
    username: str
    priority: int
    reason: str
    queue_position: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WriteGranted(Event):
    """Event when write access is granted."""
    session_id: str
    user_id: str
    username: str
    request_id: str
    queue_position: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WriteReleased(Event):
    """Event when write access is released."""
    session_id: str
    user_id: str
    username: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HeartbeatUpdated(Event):
    """Event when a heartbeat is updated."""
    session_id: str
    user_id: str
    username: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class HeartbeatTimeout(Event):
    """Event when a heartbeat times out."""
    session_id: str
    user_id: str
    username: str
    last_seen: datetime
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class QueueUpdated(Event):
    """Event when the write queue changes."""
    queue_length: int
    next_writer: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LockReleased(Event):
    """Event when lock is released."""
    session_id: str
    user_id: str
    username: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModeChanged(Event):
    """Event when collaboration mode changes."""
    mode: str  # "READ" or "WRITE"
    timestamp: datetime = field(default_factory=datetime.now)