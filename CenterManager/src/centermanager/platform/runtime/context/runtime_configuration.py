# -*- coding: utf-8 -*-
"""RuntimeConfiguration - Platform configuration."""

from dataclasses import dataclass, field


@dataclass
class RuntimeConfiguration:
    """Platform runtime configuration."""
    
    deployment_profile: str = "standalone"  # standalone, collaborative, server
    app_version: str = "0.1.0"
    app_name: str = "CenterManager"
    heartbeat_interval: int = 10
    lock_timeout: int = 60
    sync_policy: str = "on_startup_if_outdated"
    
    # Feature flags
    collaboration_enabled: bool = False
    synchronization_enabled: bool = False
    
    @classmethod
    def from_app_config(cls, config: dict) -> "RuntimeConfiguration":
        """Create from application config."""
        return cls(
            deployment_profile=config.get("deployment", {}).get("profile", "standalone"),
            app_version=config.get("application", {}).get("version", "0.1.0"),
            app_name=config.get("application", {}).get("name", "CenterManager"),
            heartbeat_interval=config.get("collaboration", {}).get("heartbeat_interval", 10),
            lock_timeout=config.get("collaboration", {}).get("lock_timeout", 60),
            sync_policy=config.get("collaboration", {}).get("sync_policy", "on_startup_if_outdated"),
            collaboration_enabled=bool(config.get("collaboration", {})),
            synchronization_enabled=bool(config.get("git", {})),
        )