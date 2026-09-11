# -*- coding: utf-8 -*-
"""SynchronizationPolicy - Determines when to sync."""

from enum import Enum
from dataclasses import dataclass


class SyncPolicy(Enum):
    """Synchronization policies."""
    ALWAYS = "always"
    ON_STARTUP_IF_OUTDATED = "on_startup_if_outdated"
    BACKGROUND = "background"
    MANUAL = "manual"


@dataclass
class SynchronizationPolicy:
    """Policy for synchronization decisions."""
    
    policy: SyncPolicy = SyncPolicy.ON_STARTUP_IF_OUTDATED
    
    def should_sync_on_startup(self, is_outdated: bool = False) -> bool:
        """Determine if sync should run on startup."""
        if self.policy == SyncPolicy.ALWAYS:
            return True
        if self.policy == SyncPolicy.ON_STARTUP_IF_OUTDATED:
            return is_outdated
        if self.policy == SyncPolicy.BACKGROUND:
            return True
        return False
    
    def should_sync_background(self) -> bool:
        """Determine if background sync is allowed."""
        return self.policy == SyncPolicy.BACKGROUND
    
    def should_sync_manual(self) -> bool:
        """Determine if manual sync is allowed."""
        return self.policy != SyncPolicy.MANUAL
    
    @classmethod
    def from_config(cls, config: dict) -> "SynchronizationPolicy":
        """Create policy from configuration."""
        policy_name = config.get("sync_policy", "on_startup_if_outdated")
        try:
            policy = SyncPolicy(policy_name)
        except ValueError:
            policy = SyncPolicy.ON_STARTUP_IF_OUTDATED
        return cls(policy=policy)