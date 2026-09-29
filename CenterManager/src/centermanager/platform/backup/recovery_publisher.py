# -*- coding: utf-8 -*-
"""Authoritative publication boundary for destructive recovery."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RecoveryPublishError(RuntimeError):
    """The restored runtime state could not be published authoritatively."""


@dataclass
class AuthoritativeRecoveryPublisher:
    # May be a RuntimeSyncService or a zero-argument resolver returning the live
    # service. The resolver form lets UI composition bind after MainWindow has
    # been re-parented without creating a second synchronization manager.
    runtime_sync_service: Any

    def _runtime_sync(self):
        candidate = self.runtime_sync_service
        if callable(candidate) and not hasattr(candidate, "publish_only"):
            candidate = candidate()
        return candidate

    def publish(
        self,
        *,
        authority: Any,
        actor_name: str,
        backup_name: str,
        expected_main_commit: Optional[str] = None,
    ) -> None:
        if authority is None or not bool(authority.validate()):
            raise RecoveryPublishError(
                "Exclusive recovery authority is required for authoritative publish."
            )
        runtime_sync = self._runtime_sync()
        if runtime_sync is None or not callable(getattr(runtime_sync, "publish_only", None)):
            raise RecoveryPublishError("Recovery publisher is unavailable.")

        message = f"Recovery restore: {backup_name}"
        try:
            published = runtime_sync.publish_only(
                message=message,
                user=str(actor_name or "system"),
                expected_main_commit=expected_main_commit,
            )
        except Exception as exc:
            raise RecoveryPublishError(f"Authoritative recovery publish failed: {exc}") from exc

        if not published:
            raise RecoveryPublishError("Authoritative recovery publish failed.")
        if not bool(authority.validate()):
            raise RecoveryPublishError(
                "Exclusive recovery authority was lost during authoritative publish."
            )
        logger.info("Authoritative recovery publish completed for %s", backup_name)
