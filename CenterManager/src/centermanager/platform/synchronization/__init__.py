# -*- coding: utf-8 -*-
"""Synchronization - Platform synchronization infrastructure."""

from .synchronization_manager import SynchronizationManager
from .synchronization_provider import SynchronizationProvider
from .git_provider import GitSynchronizationProvider
from .synchronization_policy import SynchronizationPolicy, SyncPolicy
from .version_resolver import VersionResolver, VersionStatus
from .synchronization_result import SynchronizationResult, SyncResult
from .retry_policy import RetryPolicy
from .events import (
    SynchronizationStarted,
    SynchronizationFinished,
    SynchronizationFailed,
    SynchronizationCancelled,
    VersionChecked,
    ProviderUnavailable,
)
from .exceptions import (
    SynchronizationError,
    AuthenticationFailedError,
    RemoteUnavailableError,
    RepositoryBusyError,
    RepositoryConflictError,
    RepositoryDetachedError,
    BranchMismatchError,
    RepositoryCorruptedError,
    GitNotInstalledError,
    InvalidCredentialsError,
    CloneFailedError,
    FetchFailedError,
    PullFailedError,
    PushFailedError,
)

__all__ = [
    "SynchronizationManager",
    "SynchronizationProvider",
    "GitSynchronizationProvider",
    "SynchronizationPolicy",
    "SyncPolicy",
    "VersionResolver",
    "VersionStatus",
    "SynchronizationResult",
    "SyncResult",
    "RetryPolicy",
    "SynchronizationStarted",
    "SynchronizationFinished",
    "SynchronizationFailed",
    "SynchronizationCancelled",
    "VersionChecked",
    "ProviderUnavailable",
    "SynchronizationError",
    "AuthenticationFailedError",
    "RemoteUnavailableError",
    "RepositoryBusyError",
    "RepositoryConflictError",
    "RepositoryDetachedError",
    "BranchMismatchError",
    "RepositoryCorruptedError",
    "GitNotInstalledError",
    "InvalidCredentialsError",
    "CloneFailedError",
    "FetchFailedError",
    "PullFailedError",
    "PushFailedError",
]