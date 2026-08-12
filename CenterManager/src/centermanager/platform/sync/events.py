# -*- coding: utf-8 -*-
"""Synchronization events for Runtime Auto Sync."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from centermanager.events.event import Event


@dataclass
class UpdateDetected(Event):
    """Event when a Runtime update is detected."""
    correlation_id: str
    session_id: str
    current_version: int
    remote_version: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationDeferred(Event):
    """Event when synchronization is deferred."""
    correlation_id: str
    session_id: str
    reason: str
    current_version: int
    remote_version: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationStarted(Event):
    """Event when synchronization starts."""
    correlation_id: str
    session_id: str
    current_version: int
    remote_version: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationCompleted(Event):
    """Event when synchronization completes successfully."""
    correlation_id: str
    session_id: str
    old_version: int
    new_version: int
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationSkipped(Event):
    """Event when synchronization is skipped."""
    correlation_id: str
    session_id: str
    reason: str
    current_version: int
    remote_version: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationFailed(Event):
    """Event when synchronization fails."""
    correlation_id: str
    session_id: str
    error: str
    current_version: int
    remote_version: Optional[int] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ReloadRequired(Event):
    """Event when reload is required."""
    correlation_id: str
    session_id: str
    new_version: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SyncStatusChanged(Event):
    """Event when sync status changes."""
    correlation_id: str
    session_id: str
    old_status: str
    new_status: str
    timestamp: datetime = field(default_factory=datetime.now)