# -*- coding: utf-8 -*-
"""Authoritative publication boundary for destructive recovery.

A successful local restore is not complete until the restored runtime database is
published through the synchronization provider while exclusive RecoveryAuthority
is still held.  This adapter deliberately reuses the existing safe publish-only
pipeline (which materializes the runtime database and performs the provider's
optimistic-main check) without entering normal CollaborationManager WRITE mode.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RecoveryPublishError(RuntimeError):
    """The restored runtime state could not be published authoritatively."""


@dataclass
class AuthoritativeRecoveryPublisher:
    runtime_sync_service: Any

    def publish(
        self,
        *,
        authority: Any,
        actor_name: str,
        backup_name: str,
        expected_main_commit: Optional[str] = None,
    ) -> None:
        """Publish restored state while proving recovery authority is still live.

        Fail closed before and after publication.  The postcondition prevents a
        caller from treating a publish as authoritative if the recovery lease was
        lost during the remote operation.
        """
        if authority is None or not bool(authority.validate()):
            raise RecoveryPublishError(
                "Exclusive recovery authority is required for authoritative publish."
            )
        if self.runtime_sync_service is None:
            raise RecoveryPublishError("Recovery publisher is unavailable.")

        message = f"Recovery restore: {backup_name}"
        try:
            published = self.runtime_sync_service.publish_only(
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
