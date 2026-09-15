# -*- coding: utf-8 -*-
"""ConfigurationContext - Platform configuration."""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ConfigurationContext:
    """Platform configuration values."""
    
    app_name: str = "CenterManager"
    app_version: str = "0.1.0"
    heartbeat_interval: int = 10
    lock_timeout: int = 60
    sync_policy: str = "on_startup_if_outdated"
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    
    @classmethod
    def from_app_config(cls, config: Dict[str, Any]) -> "ConfigurationContext":
        return cls(
            app_name=config.get("application", {}).get("name", "CenterManager"),
            app_version=config.get("application", {}).get("version", "0.1.0"),
            heartbeat_interval=config.get("collaboration", {}).get("heartbeat_interval", 10),
            lock_timeout=config.get("collaboration", {}).get("lock_timeout", 60),
            sync_policy=config.get("collaboration", {}).get("sync_policy", "on_startup_if_outdated"),
            feature_flags=config.get("features", {}),
        )