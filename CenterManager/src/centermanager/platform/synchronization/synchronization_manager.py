# -*- coding: utf-8 -*-
"""SynchronizationManager - Coordinates synchronization workflow."""

import logging
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable

from .synchronization_provider import SynchronizationProvider
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

from centermanager.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class SynchronizationManager:
    """
    Coordinates synchronization workflow.
    """

    def __init__(
        self,
        provider: Optional[SynchronizationProvider],
        policy: Optional[SynchronizationPolicy] = None,
        event_bus: Optional[EventBus] = None,
        retry_policy: Optional[RetryPolicy] = None,
    ):
        self._provider = provider
        self._policy = policy or SynchronizationPolicy()
        self._event_bus = event_bus
        self._retry_policy = retry_policy or RetryPolicy()
        self._is_syncing = False
        self._last_result: Optional[SynchronizationResult] = None
        self._correlation_id: Optional[str] = None

    def clone(self, progress_callback: Optional[Callable] = None) -> SynchronizationResult:
        """Clone repository from remote."""
        if self._provider is None:
            return SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Synchronization provider is not available",
                provider="none",
                started_at=datetime.now(),
            )

        correlation_id = str(uuid.uuid4())
        self._correlation_id = correlation_id
        start_time = time.time()

        logger.info(f"[{correlation_id}] Cloning repository")

        try:
            if not self._provider.connect():
                return SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Failed to connect provider",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )

            if hasattr(self._provider, 'clone'):
                self._provider.clone(progress_callback)
                result = SynchronizationResult(
                    result=SyncResult.SUCCESS,
                    message="Repository cloned successfully",
                    provider=self._provider.name(),
                    duration_ms=(time.time() - start_time) * 1000,
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                )
                self._last_result = result
                return result
            else:
                return SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Provider does not support clone",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )

        except Exception as e:
            logger.exception(f"[{correlation_id}] Clone failed: {e}")
            result = SynchronizationResult(
                result=SyncResult.FAILED,
                message=str(e),
                provider=self._provider.name(),
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            self._last_result = result
            return result

    def check_updates(self) -> SynchronizationResult:
        """Check for updates without performing sync."""
        if self._provider is None:
            return SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Synchronization provider is not available",
                provider="none",
                started_at=datetime.now(),
            )

        correlation_id = str(uuid.uuid4())
        self._correlation_id = correlation_id
        start_time = time.time()

        logger.info(f"[{correlation_id}] Checking updates")

        if not self._provider.health():
            result = SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Provider is unavailable",
                provider=self._provider.name(),
                started_at=datetime.now(),
            )
            self._publish_event(ProviderUnavailable(
                correlation_id=correlation_id,
                provider=self._provider.name(),
            ))
            self._last_result = result
            return result

        if not self._provider.connect():
            result = SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Failed to connect to provider",
                provider=self._provider.name(),
                started_at=datetime.now(),
            )
            self._last_result = result
            return result

        try:
            remote_manifest = self._provider.remote_manifest()
            remote_version = remote_manifest.get("runtime_version") if remote_manifest else None
            logger.info(f"[{correlation_id}] Remote version: {remote_version}")
        except Exception as e:
            logger.error(f"[{correlation_id}] Failed to get remote manifest: {e}")
            remote_version = None

        current_version = 0
        if hasattr(self._provider, 'current_version'):
            current_version = self._provider.current_version()

        resolver = VersionResolver()
        status = resolver.resolve(current_version, remote_version)

        self._publish_event(VersionChecked(
            correlation_id=correlation_id,
            current_version=current_version,
            remote_version=remote_version,
            status=status.value,
            provider=self._provider.name(),
        ))

        needs_sync = resolver.needs_sync(current_version, remote_version)

        result = SynchronizationResult(
            result=SyncResult.NO_CHANGE if not needs_sync else SyncResult.SUCCESS,
            message="Version check completed",
            provider=self._provider.name(),
            current_version=current_version,
            remote_version=remote_version,
            duration_ms=(time.time() - start_time) * 1000,
            started_at=datetime.now(),
            finished_at=datetime.now(),
        )
        self._last_result = result
        return result

    def begin_sync(self, message: str = "", user: str = "system") -> SynchronizationResult:
        """Execute synchronization workflow."""
        if self._provider is None:
            return SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Synchronization provider is not available",
                provider="none",
                started_at=datetime.now(),
            )

        if self._is_syncing:
            return SynchronizationResult(
                result=SyncResult.FAILED,
                message="Synchronization already in progress",
                provider=self._provider.name(),
            )

        correlation_id = str(uuid.uuid4())
        self._correlation_id = correlation_id
        self._is_syncing = True
        start_time = time.time()

        logger.info(f"[{correlation_id}] Beginning synchronization")

        self._publish_event(SynchronizationStarted(
            correlation_id=correlation_id,
            provider=self._provider.name(),
            policy=self._policy.policy.value,
        ))

        try:
            if not self._provider.health():
                result = SynchronizationResult(
                    result=SyncResult.OFFLINE,
                    message="Provider unavailable",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._publish_event(ProviderUnavailable(
                    correlation_id=correlation_id,
                    provider=self._provider.name(),
                ))
                self._last_result = result
                return result

            if not self._provider.connect():
                result = SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Failed to connect to provider",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._publish_event(SynchronizationFailed(
                    correlation_id=correlation_id,
                    provider=self._provider.name(),
                    error=result.message,
                ))
                self._last_result = result
                return result

            fetch_result = self._retry_policy.execute(
                self._provider.fetch,
                name="fetch"
            )

            if not fetch_result:
                result = SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Fetch failed after retries",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._publish_event(SynchronizationFailed(
                    correlation_id=correlation_id,
                    provider=self._provider.name(),
                    error=result.message,
                ))
                self._last_result = result
                return result

            pull_result = self._retry_policy.execute(
                self._provider.pull,
                name="pull"
            )

            if not pull_result:
                result = SynchronizationResult(
                    result=SyncResult.CONFLICT,
                    message="Pull failed (conflict)",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._publish_event(SynchronizationFailed(
                    correlation_id=correlation_id,
                    provider=self._provider.name(),
                    error="Pull failed - conflict detected",
                ))
                self._last_result = result
                return result

            if message:
                publish_result = self._retry_policy.execute(
                    lambda: self._provider.publish(message, user),
                    name="publish"
                )

                if not publish_result:
                    result = SynchronizationResult(
                        result=SyncResult.FAILED,
                        message="Publish failed after retries",
                        provider=self._provider.name(),
                        started_at=datetime.now(),
                    )
                    self._publish_event(SynchronizationFailed(
                        correlation_id=correlation_id,
                        provider=self._provider.name(),
                        error=result.message,
                    ))
                    self._last_result = result
                    return result

            result = SynchronizationResult(
                result=SyncResult.SUCCESS,
                message="Synchronization completed successfully",
                provider=self._provider.name(),
                duration_ms=(time.time() - start_time) * 1000,
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )

            self._publish_event(SynchronizationFinished(
                correlation_id=correlation_id,
                provider=self._provider.name(),
                result=result.result.value,
                duration_ms=result.duration_ms,
            ))

            self._last_result = result
            return result

        except Exception as e:
            logger.exception(f"[{correlation_id}] Sync failed: {e}")
            result = SynchronizationResult(
                result=SyncResult.FAILED,
                message=str(e),
                provider=self._provider.name(),
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            self._publish_event(SynchronizationFailed(
                correlation_id=correlation_id,
                provider=self._provider.name(),
                error=str(e),
            ))
            self._last_result = result
            return result

        finally:
            self._is_syncing = False

    def publish_only(self, message: str = "", user: str = "system") -> SynchronizationResult:
        """
        Publish local changes WITHOUT fetching or pulling first.
        This is for Writer Finish Editing - only commit and push.
        """
        if self._provider is None:
            return SynchronizationResult(
                result=SyncResult.OFFLINE,
                message="Synchronization provider is not available",
                provider="none",
                started_at=datetime.now(),
            )

        if self._is_syncing:
            return SynchronizationResult(
                result=SyncResult.FAILED,
                message="Synchronization already in progress",
                provider=self._provider.name(),
            )

        correlation_id = str(uuid.uuid4())
        self._correlation_id = correlation_id
        self._is_syncing = True
        start_time = time.time()

        logger.info(f"[{correlation_id}] Publishing local changes (no fetch/pull)")

        try:
            if not self._provider.health():
                result = SynchronizationResult(
                    result=SyncResult.OFFLINE,
                    message="Provider unavailable",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._last_result = result
                return result

            if not self._provider.connect():
                result = SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Failed to connect to provider",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                )
                self._last_result = result
                return result

            if not self._provider.publish(message, user):
                result = SynchronizationResult(
                    result=SyncResult.FAILED,
                    message="Publish failed",
                    provider=self._provider.name(),
                    started_at=datetime.now(),
                    finished_at=datetime.now(),
                )
                self._last_result = result
                return result

            result = SynchronizationResult(
                result=SyncResult.SUCCESS,
                message="Publish completed successfully",
                provider=self._provider.name(),
                duration_ms=(time.time() - start_time) * 1000,
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            self._last_result = result
            return result

        except Exception as e:
            logger.exception(f"[{correlation_id}] Publish failed: {e}")
            result = SynchronizationResult(
                result=SyncResult.FAILED,
                message=str(e),
                provider=self._provider.name(),
                started_at=datetime.now(),
                finished_at=datetime.now(),
            )
            self._last_result = result
            return result

        finally:
            self._is_syncing = False

    def cancel(self) -> bool:
        """Cancel current synchronization."""
        if not self._is_syncing:
            return False
        self._is_syncing = False
        if self._correlation_id:
            self._publish_event(SynchronizationCancelled(
                correlation_id=self._correlation_id,
                provider=self._provider.name(),
            ))
        logger.info(f"[{self._correlation_id}] Synchronization cancelled")
        return True

    def provider(self) -> Optional[SynchronizationProvider]:
        return self._provider

    def policy(self) -> SynchronizationPolicy:
        return self._policy

    def last_result(self) -> Optional[SynchronizationResult]:
        return self._last_result

    def is_syncing(self) -> bool:
        return self._is_syncing

    def _publish_event(self, event) -> None:
        if self._event_bus:
            self._event_bus.publish(event)