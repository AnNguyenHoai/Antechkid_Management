# -*- coding: utf-8 -*-
"""Runtime Auto Sync - Platform automatic synchronization."""

# Public RuntimeSyncService is the fail-closed authoritative implementation.
# It extends the WAL-safe/UI-safe handoff layer and additionally requires an
# exact fresh origin/MAIN commit before WRITE can be granted.
from .authoritative_runtime_sync_service import RuntimeSyncService
from .status import SyncStatus
from .auto_pull_policy import AutoPullPolicy
from .reload_decision_service import ReloadDecisionService, ReloadDecision, ReloadState
from .events import (
    UpdateDetected,
    SynchronizationDeferred,
    SynchronizationStarted,
    SynchronizationCompleted,
    SynchronizationSkipped,
    SynchronizationFailed,
    ReloadRequired,
    SyncStatusChanged,
)
from .startup_sync import StartupSynchronization

__all__ = [
    "RuntimeSyncService",
    "SyncStatus",
    "AutoPullPolicy",
    "ReloadDecisionService",
    "ReloadDecision",
    "ReloadState",
    "UpdateDetected",
    "SynchronizationDeferred",
    "SynchronizationStarted",
    "SynchronizationCompleted",
    "SynchronizationSkipped",
    "SynchronizationFailed",
    "ReloadRequired",
    "SyncStatusChanged",
    "StartupSynchronization",
]
