# -*- coding: utf-8 -*-
"""Synchronization events for Runtime EventBus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from centermanager.events.event import Event


@dataclass
class SynchronizationStarted(Event):
    """Event when synchronization begins."""
    correlation_id: str
    provider: str
    policy: str
    current_version: Optional[int] = None
    remote_version: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationFinished(Event):
    """Event when synchronization completes successfully."""
    correlation_id: str
    provider: str
    result: str  # SyncResult value
    current_version: Optional[int] = None
    remote_version: Optional[int] = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationFailed(Event):
    """Event when synchronization fails."""
    correlation_id: str
    provider: str
    error: str
    current_version: Optional[int] = None
    remote_version: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SynchronizationCancelled(Event):
    """Event when synchronization is cancelled."""
    correlation_id: str
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VersionChecked(Event):
    """Event when version check is performed."""
    correlation_id: str
    current_version: int
    remote_version: Optional[int]
    status: str  # VersionStatus value
    provider: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ProviderUnavailable(Event):
    """Event when synchronization provider is unavailable."""
    correlation_id: str
    provider: str
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)