# -*- coding: utf-8 -*-
from .event import Event
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# REMOVED: from centermanager.platform.collaboration.mode_manager import CollaborationMode   # if needed for ModeChanged

@dataclass
class HeartbeatStarted(Event):
    owner: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class HeartbeatStopped(Event):
    owner: str
    session_id: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RecoveryStarted(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RecoveryCompleted(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RecoveryFailed(Event):
    error: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class BackupCreated(Event):
    backup_path: str
    label: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class BackupFailed(Event):
    error: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class HealthChanged(Event):
    old_status: str
    new_status: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RetryStarted(Event):
    operation: str
    attempt: int
    max_retries: int
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RetryFinished(Event):
    operation: str
    attempt: int
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class WriteRequested(Event):
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class WriteGranted(Event):
    session_id: str
    owner: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class WriteReleased(Event):
    owner: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModeChanged(Event):
    mode: str   # "READ" or "WRITE"
    timestamp: datetime = field(default_factory=datetime.now)