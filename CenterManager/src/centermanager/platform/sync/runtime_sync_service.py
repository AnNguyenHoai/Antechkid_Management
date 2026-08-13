# -*- coding: utf-8 -*-
"""RuntimeSyncService - Automatic Runtime synchronization."""

import logging
import threading
import time
import uuid
import shutil
from datetime import datetime
from typing import Optional, Callable
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus

from .status import SyncStatus
from .events import (
    UpdateDetected,
    SynchronizationDeferred,
    SynchronizationStarted as SyncStartedEvent,
    SynchronizationCompleted,
    SynchronizationSkipped,
    SynchronizationFailed,
    ReloadRequired,
    SyncStatusChanged,
)
from .auto_pull_policy import AutoPullPolicy
from .reload_decision_service import ReloadDecisionService, ReloadDecision, ReloadState

from ..synchronization import (
    SynchronizationManager,
    VersionResolver,
    VersionStatus,
    RetryPolicy,
)
from ..collaboration import CollaborationManager
from ..runtime.context_manager import RuntimeContextManager

logger = logging.getLogger(__name__)


class RuntimeSyncService:
    """
    Automatic Runtime synchronization service.
    Monitors version, executes sync, coordinates with collaboration.
    """

    def __init__(
        self,
        sync_manager: SynchronizationManager,
        collab_manager: CollaborationManager,
        context_manager: RuntimeContextManager,
        event_bus: Optional[EventBus] = None,
        policy: Optional[AutoPullPolicy] = None,
        reload_service: Optional[ReloadDecisionService] = None,
        poll_interval: int = 30,
    ):
        self._sync_manager = sync_manager
        self._collab_manager = collab_manager
        self._context_manager = context_manager
        self._event_bus = event_bus or EventBus()
        self._policy = policy or AutoPullPolicy()
        self._reload_service = reload_service or ReloadDecisionService()
        self._poll_interval = poll_interval

        # State
        self._status = SyncStatus.IDLE
        self._current_version = 0
        self._remote_version = 0
        self._last_check = None
        self._last_sync = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pending_update = False
        self._deferred_count = 0

        # Retry
        self._retry_policy = RetryPolicy(max_retries=3, retry_interval=5.0)
        self._failed_count = 0

        self._state_mutex = threading.RLock()

        logger.info(f"RuntimeSyncService initialized (poll_interval={poll_interval}s)")

    def start(self) -> None:
        """Start automatic sync service."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info("RuntimeSyncService started")

    def stop(self) -> None:
        """Stop automatic sync service."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("RuntimeSyncService stopped")

    def check_for_updates(self) -> bool:
        """Manually check for updates."""
        return self._perform_check()

    def execute_sync(self) -> bool:
        """Manually execute synchronization."""
        return self._perform_sync()

    def publish_only(self, message: str = "Finish Editing", user: str = "system") -> bool:
        """
        Publish local changes WITHOUT fetching or pulling first.
        This is the dedicated Publish operation for Writer Finish Editing.
        """
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                logger.warning("Cannot publish while synchronization is in progress")
                return False
            self._set_status(SyncStatus.SYNCHRONIZING)

        try:
            result = self._sync_manager.publish_only(
                message=message,
                user=user
            )

            if result and result.is_success():
                self._last_sync = datetime.now()
                self._failed_count = 0
                with self._state_mutex:
                    self._set_status(SyncStatus.IDLE)
                logger.info("Publish-only completed successfully")
                return True
            else:
                error = result.message if result else "Unknown error"
                logger.error(f"Publish-only failed: {error}")
                self._failed_count += 1
                with self._state_mutex:
                    self._set_status(SyncStatus.FAILED)
                return False

        except Exception as e:
            logger.exception(f"Publish-only exception: {e}")
            self._failed_count += 1
            with self._state_mutex:
                self._set_status(SyncStatus.FAILED)
            return False

    def cancel_sync(self) -> bool:
        """Cancel ongoing synchronization."""
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                self._sync_manager.cancel()
                self._set_status(SyncStatus.IDLE)
                return True
        return False

    def current_state(self) -> dict:
        """Get current sync state."""
        with self._state_mutex:
            return {
                "status": self._status.value,
                "current_version": self._current_version,
                "remote_version": self._remote_version,
                "last_check": self._last_check.isoformat() if self._last_check else None,
                "last_sync": self._last_sync.isoformat() if self._last_sync else None,
                "pending_update": self._pending_update,
                "deferred_count": self._deferred_count,
                "failed_count": self._failed_count,
            }

    def _sync_loop(self) -> None:
        """Main sync loop."""
        while self._running:
            try:
                self._perform_check()

                if self._pending_update:
                    self._attempt_sync()

                time.sleep(self._poll_interval)
            except Exception as e:
                logger.exception(f"Sync loop error: {e}")
                time.sleep(self._poll_interval)

    def _perform_check(self) -> bool:
        """Perform version check."""
        corr_id = str(uuid.uuid4())
        session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"

        with self._state_mutex:
            self._set_status(SyncStatus.CHECKING)
            self._last_check = datetime.now()

        try:
            result = self._sync_manager.check_updates()
            remote_version = result.remote_version or 0
            current_version = result.current_version or 0

            with self._state_mutex:
                self._current_version = current_version
                self._remote_version = remote_version
                self._pending_update = remote_version > current_version

            logger.info(f"[{corr_id}] Version check: current={current_version}, remote={remote_version}, pending={self._pending_update}")

            if self._pending_update:
                self._event_bus.publish(UpdateDetected(
                    correlation_id=corr_id,
                    session_id=session_id,
                    current_version=current_version,
                    remote_version=remote_version,
                ))

            with self._state_mutex:
                self._set_status(SyncStatus.IDLE)

            return self._pending_update

        except Exception as e:
            logger.exception(f"[{corr_id}] Version check failed: {e}")
            with self._state_mutex:
                self._set_status(SyncStatus.FAILED)
            return False

    def _attempt_sync(self) -> None:
        """Attempt to synchronize if conditions allow."""
        session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"

        has_writer = self._collab_manager.is_writing()
        queue_length = len(self._collab_manager.get_queue().get("requests", []))

        context = self._context_manager.get_context()
        is_ready = context.is_ready()

        is_healthy = self._sync_manager.provider().health()

        should, reason = self._policy.should_pull(
            is_ready=is_ready,
            has_writer=has_writer,
            queue_length=queue_length,
            is_healthy=is_healthy,
            version_status=VersionStatus.OUTDATED if self._pending_update else VersionStatus.UP_TO_DATE
        )

        if not should:
            logger.info(f"Sync deferred: {reason}")
            self._deferred_count += 1
            self._event_bus.publish(SynchronizationDeferred(
                correlation_id=str(uuid.uuid4()),
                session_id=session_id,
                reason=reason,
                current_version=self._current_version,
                remote_version=self._remote_version,
            ))
            return

        self._perform_sync()

    def _perform_sync(self) -> bool:
        """Execute synchronization workflow."""
        corr_id = str(uuid.uuid4())
        session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"
        start_time = time.time()

        with self._state_mutex:
            self._set_status(SyncStatus.SYNCHRONIZING)

        try:
            self._event_bus.publish(SyncStartedEvent(
                correlation_id=corr_id,
                session_id=session_id,
                current_version=self._current_version,
                remote_version=self._remote_version,
            ))

            def sync_op():
                return self._sync_manager.begin_sync("Auto sync", "system")

            success, result = self._retry_policy.execute_with_result(sync_op)

            duration_ms = (time.time() - start_time) * 1000

            if success and result and result.is_success():
                with self._state_mutex:
                    self._current_version = self._remote_version
                    self._pending_update = False
                    self._last_sync = datetime.now()
                    self._failed_count = 0

                # Apply runtime update
                apply_success = self._apply_runtime_update()
                if not apply_success:
                    logger.error("Failed to apply runtime update after sync")

                self._event_bus.publish(SynchronizationCompleted(
                    correlation_id=corr_id,
                    session_id=session_id,
                    old_version=result.current_version or 0,
                    new_version=result.remote_version or self._current_version,
                    duration_ms=duration_ms,
                ))

                logger.info(f"[{corr_id}] Sync completed in {duration_ms:.0f}ms")
                self._check_reload()

                with self._state_mutex:
                    self._set_status(SyncStatus.IDLE)
                return True
            else:
                error = result.message if result else "Unknown error"
                raise Exception(error)

        except Exception as e:
            logger.exception(f"[{corr_id}] Sync failed: {e}")
            self._failed_count += 1

            self._event_bus.publish(SynchronizationFailed(
                correlation_id=corr_id,
                session_id=session_id,
                error=str(e),
                current_version=self._current_version,
                remote_version=self._remote_version,
                retry_count=self._failed_count,
            ))

            with self._state_mutex:
                self._set_status(SyncStatus.FAILED)
            return False

    def _apply_runtime_update(self) -> bool:
        """
        Apply repository database to runtime database.
        Copy runtime/repository/database/center.db -> runtime/Database/center.db
        Returns True if successful.
        """
        try:
            paths = get_paths()
            repo_db = paths.runtime_root / "repository" / "database" / "center.db"
            runtime_db = paths.database_dir / "center.db"

            if not repo_db.exists():
                logger.warning("Repository database not found, skipping runtime update")
                return True

            # Copy repository DB to runtime DB
            runtime_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repo_db, runtime_db)
            logger.info(f"Runtime database updated from repository: {runtime_db}")

            # Refresh database sessions
            self._refresh_db_sessions()

            return True
        except Exception as e:
            logger.exception(f"Failed to apply runtime update: {e}")
            return False

    def _refresh_db_sessions(self) -> None:
        """
        Refresh database sessions after runtime DB update.
        This ensures SQLAlchemy sessions don't serve stale data.
        """
        try:
            from centermanager.database.session import refresh_runtime_db
            refresh_runtime_db()
            logger.info("Database sessions refreshed after runtime update")
        except Exception as e:
            logger.exception(f"Failed to refresh database sessions: {e}")

    def _check_reload(self) -> None:
        """Check if reload is required and decide."""
        state = ReloadState(
            is_writing=self._collab_manager.is_writing(),
            has_pending_queue=len(self._collab_manager.get_queue().get("requests", [])) > 0,
        )

        decision = self._reload_service.decide(state)

        if decision == ReloadDecision.RELOAD_NOW:
            corr_id = str(uuid.uuid4())
            session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"
            self._event_bus.publish(ReloadRequired(
                correlation_id=corr_id,
                session_id=session_id,
                new_version=self._current_version,
                reason="Runtime updated",
            ))
            logger.info(f"Reload required after sync (version {self._current_version})")
        elif decision == ReloadDecision.WAIT:
            logger.info("Reload deferred - conditions not met")

    def _set_status(self, status: SyncStatus) -> None:
        """Set sync status and publish event."""
        old = self._status
        self._status = status
        if old != status:
            session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"
            self._event_bus.publish(SyncStatusChanged(
                correlation_id=str(uuid.uuid4()),
                session_id=session_id,
                old_status=old.value,
                new_status=status.value,
            ))