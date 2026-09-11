# -*- coding: utf-8 -*-
"""Synchronization exceptions."""


class SynchronizationError(Exception):
    """Base synchronization exception."""
    pass


class AuthenticationFailedError(SynchronizationError):
    """Git authentication failed."""
    pass


class RemoteUnavailableError(SynchronizationError):
    """Remote repository is unavailable."""
    pass


class RepositoryBusyError(SynchronizationError):
    """Repository is busy (locked by another process)."""
    pass


class RepositoryConflictError(SynchronizationError):
    """Repository has conflicts that need manual resolution."""
    pass


class RepositoryDetachedError(SynchronizationError):
    """Repository is in detached HEAD state."""
    pass


class BranchMismatchError(SynchronizationError):
    """Local and remote branches do not match."""
    pass


class RepositoryCorruptedError(SynchronizationError):
    """Repository is corrupted."""
    pass


class GitNotInstalledError(SynchronizationError):
    """Git executable not found."""
    pass


class InvalidCredentialsError(SynchronizationError):
    """Invalid Git credentials."""
    pass


class CloneFailedError(SynchronizationError):
    """Repository clone failed."""
    pass


class FetchFailedError(SynchronizationError):
    """Fetch operation failed."""
    pass


class PullFailedError(SynchronizationError):
    """Pull operation failed."""
    pass


class PushFailedError(SynchronizationError):
    """Push operation failed."""
    pass

class PullFailedError(SynchronizationError):
    """Raised when pull operation fails."""
    pass