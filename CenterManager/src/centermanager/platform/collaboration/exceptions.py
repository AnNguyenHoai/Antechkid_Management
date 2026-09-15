# -*- coding: utf-8 -*-
"""Collaboration exceptions."""


class CollaborationError(Exception):
    """Base collaboration exception."""
    pass


class LockAlreadyHeldError(CollaborationError):
    """Lock is already held by another session."""
    pass


class LockNotHeldError(CollaborationError):
    """Lock is not held by this session."""
    pass


class LockTimeoutError(CollaborationError):
    """Lock acquisition timed out."""
    pass


class SessionNotFoundError(CollaborationError):
    """Session not found."""
    pass


class SessionExpiredError(CollaborationError):
    """Session has expired."""
    pass


class QueueEmptyError(CollaborationError):
    """Write queue is empty."""
    pass


class InvalidPriorityError(CollaborationError):
    """Invalid priority value."""
    pass


class HeartbeatTimeoutError(CollaborationError):
    """Heartbeat timeout detected."""
    pass


class CollaborationNotInitializedError(CollaborationError):
    """Collaboration manager not initialized."""
    pass