# -*- coding: utf-8 -*-
"""Deployment configuration management with secure storage for sensitive data."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from centermanager.core.paths import get_paths
from centermanager.core.secure_config import SecureConfig

logger = logging.getLogger(__name__)

DEFAULT_DEPLOYMENT_CONFIG = {
    "repository_url": "",
    "branch": "main",
    "local_path": "",  # will be set to runtime/repository
    "token": "",
    "git_executable": "",
}


class DeploymentConfig:
    """Manage deployment configuration using SecureConfig for sensitive values."""

    def __init__(self) -> None:
        self._secure = SecureConfig()
        self._config_file = get_paths().config_dir / "deployment.json"
        self._data: Dict[str, Any] = {}
        self._migrate_legacy()
        self._load()

    def _migrate_legacy(self) -> None:
        """Migrate old config to secure storage if exists."""
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                if old_data.get("token"):
                    self._secure.set("git_token", old_data["token"])
                    logger.info("Migrated git token to secure storage.")
                if old_data.get("repository_url"):
                    self._secure.set("git_repository_url", old_data["repository_url"])
                    logger.info("Migrated repository URL to secure storage.")
                # Rename old file to avoid confusion
                backup = self._config_file.with_suffix(".json.legacy")
                self._config_file.rename(backup)
                logger.info(f"Legacy config backed up to {backup}")
            except Exception as e:
                logger.warning(f"Failed to migrate legacy config: {e}")

    def _load(self) -> None:
        """Load configuration from secure storage."""
        self._data = {
            "repository_url": self._secure.get("git_repository_url", ""),
            "branch": self._secure.get("git_branch", "main"),
            "local_path": self._secure.get("git_local_path", ""),
            "token": self._secure.get("git_token", ""),
            "git_executable": self._secure.get("git_executable", ""),
        }
        # Ensure local_path default
        if not self._data["local_path"]:
            default_path = get_paths().runtime_root / "repository"
            self.set("local_path", str(default_path))

    def _save(self) -> None:
        """Save configuration to secure storage."""
        for key, value in self._data.items():
            if key == "repository_url":
                self._secure.set("git_repository_url", value)
            elif key == "branch":
                self._secure.set("git_branch", value)
            elif key == "local_path":
                self._secure.set("git_local_path", value)
            elif key == "token":
                self._secure.set("git_token", value)
            elif key == "git_executable":
                self._secure.set("git_executable", value)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self._save()

    def get_repository_url(self) -> str:
        return self._data.get("repository_url", "")

    def get_branch(self) -> str:
        return self._data.get("branch", "main")

    def get_local_path(self) -> Path:
        path_str = self._data.get("local_path", "")
        if not path_str:
            default_path = get_paths().runtime_root / "repository"
            self.set("local_path", str(default_path))
            return default_path
        return Path(path_str)

    def get_token(self) -> str:
        return self._data.get("token", "")

    def get_git_executable(self) -> str:
        return self._data.get("git_executable", "")

    def set_git_executable(self, path: str) -> None:
        self.set("git_executable", path)

    def is_configured(self) -> bool:
        """Check if repository URL is set and token exists."""
        return bool(self.get_repository_url() and self.get_token())

    def clear(self) -> None:
        self._data = DEFAULT_DEPLOYMENT_CONFIG.copy()
        self._save()