# -*- coding: utf-8 -*-
"""Platform - Core platform components."""

from .bootstrap import BootstrapManager
from .context import (
    PlatformContext,
    RuntimeContext,
    DeploymentContext,
    SessionContext,
    WorkspaceContext,
    UserContext,
    ConfigurationContext,
)
from .lifecycle import PlatformLifecycle, PlatformLifecycleState
from .workspace import WorkspaceDescriptor, WorkspaceRegistry
from .repository import (
    RepositoryManager,
    RepositoryState,
    ManifestLoader,
    RuntimeValidator,
    AtomicFileWriter,
)
from .synchronization import (
    SynchronizationManager,
    SynchronizationProvider,
    GitSynchronizationProvider,
    SynchronizationPolicy,
    SyncPolicy,
    VersionResolver,
    VersionStatus,
    SynchronizationResult,
    SyncResult,
    RetryPolicy,
)
from .collaboration import (
    CollaborationManager,
    RuntimeSession,
    RuntimeLock,
    WriteQueue,
    WriteRequest,
    HeartbeatRepository,
    HeartbeatManager,
    PresenceManager,
    Priority,
    Arbitration,
)
from .sync import (
    RuntimeSyncService,
    SyncStatus,
    AutoPullPolicy,
    ReloadDecisionService,
    ReloadDecision,
    ReloadState,
)
from .business import (
    BusinessModule,
    BusinessModuleLifecycle,
    WorkspaceRegistration,
    WriteGuard,
    ReadGuard,
    PermissionGuard,
)
from .business.module_registry import BusinessModuleRegistry   # <-- THÊM
from .runtime.context_manager import RuntimeContextManager
from .runtime.context.runtime_state import RuntimeState

__all__ = [
    "BootstrapManager",
    "PlatformContext",
    "RuntimeContext",
    "DeploymentContext",
    "SessionContext",
    "WorkspaceContext",
    "UserContext",
    "ConfigurationContext",
    "PlatformLifecycle",
    "PlatformLifecycleState",
    "WorkspaceDescriptor",
    "WorkspaceRegistry",
    "RepositoryManager",
    "RepositoryState",
    "ManifestLoader",
    "RuntimeValidator",
    "AtomicFileWriter",
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
    "CollaborationManager",
    "RuntimeSession",
    "RuntimeLock",
    "WriteQueue",
    "WriteRequest",
    "HeartbeatRepository",
    "HeartbeatManager",
    "PresenceManager",
    "Priority",
    "Arbitration",
    "RuntimeSyncService",
    "SyncStatus",
    "AutoPullPolicy",
    "ReloadDecisionService",
    "ReloadDecision",
    "ReloadState",
    "BusinessModule",
    "BusinessModuleLifecycle",
    "WorkspaceRegistration",
    "WriteGuard",
    "ReadGuard",
    "PermissionGuard",
    "BusinessModuleRegistry",   # <-- THÊM
    "RuntimeContextManager",
    "RuntimeState",
]