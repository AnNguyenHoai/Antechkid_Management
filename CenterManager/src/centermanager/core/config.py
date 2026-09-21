# -*- coding: utf-8 -*-
"""
Configuration loader for CenterManager.
...
"""
import json
import logging
import copy
from typing import Any, Dict, Optional
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.core.version import APPLICATION_VERSION

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG: Dict[str, Any] = {
    "application": {
        "name": "CenterManager",
        "version": APPLICATION_VERSION,
    }
}


def _with_runtime_identity(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return config with immutable application identity from the release asset.

    Runtime/operator configuration may persist across upgrades. Application
    name/version are release identity, not operator-owned settings, so stale
    values from an older config.json must never override the running binary.
    """
    normalized = copy.deepcopy(data)
    application = normalized.get("application")
    if not isinstance(application, dict):
        application = {}
        normalized["application"] = application
    application["name"] = "CenterManager"
    application["version"] = APPLICATION_VERSION
    return normalized


class Config:
    """Configuration container."""

    def __init__(self, data: Dict[str, Any]) -> None:
        self._data = _with_runtime_identity(data)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value using dot notation, e.g. 'application.name'."""
        parts = key.split(".")
        current = self._data
        try:
            for part in parts:
                current = current[part]
            return current
        except (KeyError, TypeError):
            return default

    def get_collaboration_settings(self) -> dict:
        """Get collaboration-specific settings."""
        return self._data.get("collaboration", {})

    def set_collaboration_settings(self, settings: dict) -> None:
        """Update collaboration settings and save."""
        self._data["collaboration"] = settings
        save_config(self._data)

    @property
    def raw(self) -> Dict[str, Any]:
        return copy.deepcopy(self._data)


_config: Optional[Config] = None


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        path: Path to config.json (defaults to runtime/Config/config.json)

    Returns:
        Dictionary with configuration data and canonical runtime identity.
    """
    if path is None:
        path = get_paths().config_file

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug(f"Configuration loaded from {path}")
        return _with_runtime_identity(data)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {path}. Using defaults.")
        return _with_runtime_identity(_DEFAULT_CONFIG)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}. Using defaults.")
        return _with_runtime_identity(_DEFAULT_CONFIG)


def save_config(data: Dict[str, Any], path: Optional[Path] = None) -> None:
    """
    Save configuration to JSON file.

    Args:
        data: Configuration dictionary.
        path: Path to config.json (defaults to runtime/Config/config.json)
    """
    if path is None:
        path = get_paths().config_file

    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _with_runtime_identity(data)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=4, ensure_ascii=False)
    logger.debug(f"Configuration saved to {path}")


def init_config() -> None:
    """Initialize global configuration. Create default if missing."""
    global _config
    path = get_paths().config_file

    if not path.exists():
        logger.info("Creating default config.json")
        save_config(_DEFAULT_CONFIG, path)

    data = load_config(path)
    _config = Config(data)


def get_config() -> Config:
    """Get the global Config singleton."""
    if _config is None:
        init_config()
    return _config
