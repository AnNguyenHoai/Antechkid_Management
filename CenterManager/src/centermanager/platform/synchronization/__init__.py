# -*- coding: utf-8 -*-
"""Synchronization - Platform synchronization infrastructure."""

from .synchronization_manager import SynchronizationManager
from .synchronization_provider import SynchronizationProvider
from .git_synchronization_provider import GitSynchronizationProvider   # <-- ĐỔI TỪ git_provider
from .git_output_safety import install_git_output_safety
from .git_credential_safety import install_git_credential_safety
from .git_commit_identity import install_portable_git_commit_identity
from .git_origin_reconciliation import install_origin_reconciliation
from .git_provider_safety import install_git_command_serialization
from .lock_acquisition_diagnostics import install_lock_acquisition_diagnostics
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

# Capture Git output as bytes before any other wrapper is installed. This avoids
# Windows locale decoder failures while preserving all later security wrappers.
install_git_output_safety(GitSynchronizationProvider)

# Credentials are supplied through GIT_ASKPASS. Never allow token-bearing URLs
# to reach subprocess argv, including the active startup-clone path.
install_git_credential_safety(GitSynchronizationProvider)

# Commit creation must work on clean Windows machines with no global Git
# identity configured. Inject author/committer identity only for commit and
# commit-tree subprocesses; never mutate host-global Git configuration.
install_portable_git_commit_identity(GitSynchronizationProvider)

# Runtime clones can outlive configuration changes. Reconcile the Git origin
# after the provider opens an existing repository so sync operations always
# target the configured repository without rewriting the provider implementation.
install_origin_reconciliation(GitSynchronizationProvider)

# A CollaborationPoller and the application thread can access one provider at
# the same time. Serialize subprocess-based Git access per provider instance;
# different clients/providers remain independent.
install_git_command_serialization(GitSynchronizationProvider)

# Preserve the exact reason a distributed write-lock acquisition failed.  This
# wrapper runs after the Git safety wrappers so any subprocess diagnostics have
# already passed through credential/output sanitization.
install_lock_acquisition_diagnostics(GitSynchronizationProvider)

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
