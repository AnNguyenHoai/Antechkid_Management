# -*- coding: utf-8 -*-
"""RuntimeSyncService - Automatic Runtime synchronization."""

import logging
import threading
import time
import uuid
import shutil
import json
import os
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
from .qt_event_bus import ThreadSafeEventBusProxy

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
        poll_interval: int = 5,
    ):
        self._sync_manager = sync_manager
        self._collab_manager = collab_manager
        self._context_manager = context_manager
        self._event_bus = ThreadSafeEventBusProxy(event_bus or EventBus())
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
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        logger.info("RuntimeSyncService started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("RuntimeSyncService stopped")

    def check_for_updates(self) -> bool:
        logger.info("Manual check_for_updates triggered")
        return self._perform_check()

    def execute_write_handoff_sync(self) -> bool:
        """Synchronize runtime state before a queued writer starts editing.

        This deliberately bypasses AutoPullPolicy. Background sync is deferred
        while a queue exists, but the queue handoff is a mandatory consistency
        boundary.
        """
        provider = self._sync_manager.provider() if self._sync_manager else None
        if provider is None:
            logger.warning("Write handoff sync unavailable: no synchronization provider")
            return False
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                logger.warning("Write handoff sync blocked: synchronization already in progress")
                return False
        try:
            check = self._sync_manager.check_updates()
            remote_version = check.remote_version
            current_version = self._get_repository_version()
            logger.info("Write handoff sync check: current=%s, remote=%s", current_version, remote_version)
            if remote_version is None:
                return False
            if remote_version > current_version:
                with self._state_mutex:
                    self._current_version = current_version
                    self._remote_version = remote_version
                    self._pending_update = True
                if not self._perform_sync():
                    return False
            elif remote_version < current_version:
                logger.error("Write handoff refused: local repository version %s ahead of remote %s", current_version, remote_version)
                return False

            paths = get_paths()
            runtime_manifest = paths.runtime_root / "manifest.json"
            runtime_version = None
            if runtime_manifest.exists():
                with open(runtime_manifest, "r", encoding="utf-8") as f:
                    runtime_version = json.load(f).get("runtime_version")
            repository_version = self._get_repository_version()
            if runtime_version != remote_version or repository_version != remote_version:
                logger.error(
                    "Write handoff verification failed: runtime=%s repository=%s remote=%s",
                    runtime_version, repository_version, remote_version,
                )
                return False
            logger.info("Write handoff sync completed and verified at version %s", remote_version)
            return True
        except Exception as exc:
            logger.exception("Write handoff sync failed: %s", exc)
            return False

    def execute_sync(self) -> bool:
        return self._perform_sync()

    def publish_only(self, message: str = "Finish Editing", user: str = "system", expected_main_commit: Optional[str] = None) -> bool:
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                logger.warning("Cannot publish while synchronization is in progress")
                return False
            self._set_status(SyncStatus.SYNCHRONIZING)

        try:
            result = self._sync_manager.publish_only(message=message, user=user, expected_main_commit=expected_main_commit)

            if result and result.is_success():
                self._last_sync = datetime.now()
                self._failed_count = 0
                self._current_version = self._get_repository_version()
                with self._state_mutex:
                    self._set_status(SyncStatus.IDLE)
                self.check_for_updates()
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
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                self._sync_manager.cancel()
                self._set_status(SyncStatus.IDLE)
                return True
        return False

    def current_state(self) -> dict:
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
        while self._running:
            try:
                self._perform_check()
                if self._pending_update:
                    self._attempt_sync()
                time.sleep(self._poll_interval)
            except Exception as e:
                logger.exception(f"Sync loop error: {e}")
                time.sleep(self._poll_interval)

    def _get_repository_version(self) -> int:
        try:
            paths = get_paths()
            manifest_path = paths.runtime_root / "repository" / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("runtime_version", 0)
            else:
                logger.warning(f"Repository manifest not found at {manifest_path}")
                return 0
        except Exception as e:
            logger.warning(f"Failed to read repository manifest: {e}")
            return 0

    def _perform_check(self) -> bool:
        corr_id = str(uuid.uuid4())
        session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"

        with self._state_mutex:
            self._set_status(SyncStatus.CHECKING)
            self._last_check = datetime.now()

        try:
            current_version = self._get_repository_version()
            result = self._sync_manager.check_updates()
            remote_version = result.remote_version

            with self._state_mutex:
                self._current_version = current_version
                self._remote_version = remote_version if remote_version is not None else 0
                self._pending_update = remote_version is not None and remote_version > current_version

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
        session_id = self._collab_manager.get_session().session_id if self._collab_manager.get_session() else "unknown"

        has_writer = self._collab_manager.is_writing()
        queue_length = len(self._collab_manager.get_queue().get("requests", []))

        context = self._context_manager.get_context()
        is_ready = context.runtime.is_ready()

        is_healthy = self._sync_manager.provider().health()

        if self._remote_version is None:
            version_status = VersionStatus.REMOTE_UNAVAILABLE
        elif self._remote_version > self._current_version:
            version_status = VersionStatus.OUTDATED
        elif self._remote_version == self._current_version:
            version_status = VersionStatus.UP_TO_DATE
        else:
            version_status = VersionStatus.CONFLICT

        should, reason = self._policy.should_pull(
            is_ready=is_ready,
            has_writer=has_writer,
            queue_length=queue_length,
            is_healthy=is_healthy,
            version_status=version_status
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
                new_version = self._get_repository_version()

                with self._state_mutex:
                    self._current_version = new_version
                    self._pending_update = False
                    self._last_sync = datetime.now()
                    self._failed_count = 0

                apply_success = self._apply_runtime_update()
                if not apply_success:
                    logger.error("Failed to apply runtime update after sync")

                self._event_bus.publish(SynchronizationCompleted(
                    correlation_id=corr_id,
                    session_id=session_id,
                    old_version=result.current_version or 0,
                    new_version=self._current_version,
                    duration_ms=duration_ms,
                ))

                logger.info(f"[{corr_id}] Sync completed in {duration_ms:.0f}ms, new version={self._current_version}")
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
        try:
            paths = get_paths()
            repo_db = paths.runtime_root / "repository" / "database" / "center.db"
            runtime_db = paths.database_dir / "center.db"

            if not repo_db.exists():
                logger.warning("Repository database not found, skipping runtime update")
                return True

            runtime_db.parent.mkdir(parents=True, exist_ok=True)
            with open(repo_db, 'rb') as fsrc:
                with open(runtime_db, 'wb') as fdst:
                    fdst.write(fsrc.read())
                    fdst.flush()
                    os.fsync(fdst.fileno())
            logger.info(f"Runtime database updated from repository: {runtime_db}")

            repo_manifest = paths.runtime_root / "repository" / "manifest.json"
            runtime_manifest = paths.runtime_root / "manifest.json"
            if repo_manifest.exists():
                with open(repo_manifest, 'rb') as fsrc:
                    with open(runtime_manifest, 'wb') as fdst:
                        fdst.write(fsrc.read())
                        fdst.flush()
                        os.fsync(fdst.fileno())
                logger.info(f"Runtime manifest updated from repository: {runtime_manifest}")

                # Đồng bộ metadata version.json với repository manifest
                with open(repo_manifest, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                runtime_version = manifest_data.get("runtime_version")
                if runtime_version is not None:
                    meta_version_path = paths.metadata_dir / "version.json"
                    meta_version_path.parent.mkdir(parents=True, exist_ok=True)
                    if meta_version_path.exists():
                        with open(meta_version_path, 'r', encoding='utf-8') as f:
                            meta_data = json.load(f)
                    else:
                        meta_data = {}
                    meta_data["platform_version"] = runtime_version
                    meta_data.pop("pending_version", None)
                    with open(meta_version_path, 'w', encoding='utf-8') as f:
                        json.dump(meta_data, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    logger.info(f"Metadata version.json updated to platform_version={runtime_version}")

            self._refresh_db_sessions()
            return True
        except Exception as e:
            logger.exception(f"Failed to apply runtime update: {e}")
            return False

    def _refresh_db_sessions(self) -> None:
        try:
            from centermanager.database.session import refresh_runtime_db
            refresh_runtime_db()
            logger.info("Database sessions refreshed after runtime update")
        except Exception as e:
            logger.exception(f"Failed to refresh database sessions: {e}")

    def _check_reload(self) -> None:
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
