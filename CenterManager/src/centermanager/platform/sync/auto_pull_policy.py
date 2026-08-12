# -*- coding: utf-8 -*-
"""AutoPullPolicy - Determines when auto pull should occur."""

from dataclasses import dataclass
from typing import Optional

from centermanager.platform.synchronization import VersionResolver, VersionStatus


@dataclass
class AutoPullPolicy:
    """
    Policy for automatic pull decisions.
    Conditions: Platform READY, No Active Writer, Queue Empty, Repository Healthy.
    """

    require_ready: bool = True
    require_no_writer: bool = True
    require_queue_empty: bool = True
    require_repository_healthy: bool = True

    def should_pull(
        self,
        is_ready: bool,
        has_writer: bool,
        queue_length: int,
        is_healthy: bool,
        version_status: VersionStatus,
    ) -> tuple[bool, str]:
        """
        Determine if auto pull should proceed.
        Returns (should_pull, reason).
        """
        if self.require_ready and not is_ready:
            return False, "Platform not ready"

        if self.require_no_writer and has_writer:
            return False, "Writer active"

        if self.require_queue_empty and queue_length > 0:
            return False, "Write queue not empty"

        if self.require_repository_healthy and not is_healthy:
            return False, "Repository not healthy"

        if version_status not in (VersionStatus.OUTDATED, VersionStatus.UNKNOWN):
            return False, f"Version status: {version_status.value}"

        return True, "All conditions met"