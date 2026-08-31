# -*- coding: utf-8 -*-
"""Collaboration - Platform collaboration runtime."""

from .collaboration_manager import CollaborationManager, WriteRequestResult, WriteRequestInfo
from .false_waiting_guard import install_false_waiting_guard

# Keep the restored CollaborationManager implementation intact and install the
# narrow false-WAITING protection at the package boundary. This avoids changing
# queue/arbitration APIs while ensuring a free/stale remote lock cannot be shown
# as WAITING to the user.
install_false_waiting_guard(CollaborationManager)

from .runtime_session import RuntimeSession
from .runtime_lock import RuntimeLock
from .write_queue import WriteQueue, WriteRequest
from .heartbeat import HeartbeatRepository, HeartbeatManager
from .presence_manager import PresenceManager
from .arbitration import Priority, Arbitration
from .events import (
    SessionStarted,
    SessionEnded,
    WriteRequested,
    WriteGranted,
    WriteReleased,
    HeartbeatUpdated,
    HeartbeatTimeout,
    QueueUpdated,
    LockReleased,
    ModeChanged,
)
from .exceptions import (
    CollaborationError,
    LockAlreadyHeldError,
    LockNotHeldError,
    LockTimeoutError,
    SessionNotFoundError,
    SessionExpiredError,
    QueueEmptyError,
    InvalidPriorityError,
    HeartbeatTimeoutError,
    CollaborationNotInitializedError,
)
from .mode_manager import ModeManager, CollaborationMode
from .lock_manager import LockManager
from .edit_session_manager import EditSessionManager
from .json_lock_repository import JsonLockRepository
from .json_metadata_repository import JsonMetadataRepository
from .metadata_repository import MetadataRepository
from .lock_repository import LockRepository
from .poller import CollaborationPoller, CollaborationSnapshot, CollaborationStateChanged, PollerMode

__all__ = [
    "CollaborationManager",
    "WriteRequestResult",
    "WriteRequestInfo",
    "RuntimeSession",
    "RuntimeLock",
    "WriteQueue",
    "WriteRequest",
    "HeartbeatRepository",
    "HeartbeatManager",
    "PresenceManager",
    "Priority",
    "Arbitration",
    "SessionStarted",
    "SessionEnded",
    "WriteRequested",
    "WriteGranted",
    "WriteReleased",
    "HeartbeatUpdated",
    "HeartbeatTimeout",
    "QueueUpdated",
    "LockReleased",
    "ModeChanged",
    "CollaborationError",
    "LockAlreadyHeldError",
    "LockNotHeldError",
    "LockTimeoutError",
    "SessionNotFoundError",
    "SessionExpiredError",
    "QueueEmptyError",
    "InvalidPriorityError",
    "HeartbeatTimeoutError",
    "CollaborationNotInitializedError",
    "ModeManager",
    "CollaborationMode",
    "LockManager",
    "EditSessionManager",
    "JsonLockRepository",
    "JsonMetadataRepository",
    "MetadataRepository",
    "LockRepository",
    "CollaborationPoller",
    "CollaborationSnapshot",
    "CollaborationStateChanged",
    "PollerMode",
]
