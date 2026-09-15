# -*- coding: utf-8 -*-
"""
Version Manager - manages platform version with pending version support.
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from centermanager.core.paths import get_paths
from centermanager.platform.collaboration.metadata_repository import MetadataRepository
from centermanager.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class VersionManager:
    def __init__(self, metadata_repository: MetadataRepository, event_bus: EventBus):
        self._metadata_repository = metadata_repository
        self._event_bus = event_bus
        self._version_cache = None

    def get_current_version(self) -> int:
        """Get current published platform version."""
        data = self._metadata_repository.load_version()
        return data.get("platform_version", 1)

    def get_pending_version(self) -> Optional[int]:
        """Get pending version if any (prepared but not published)."""
        data = self._metadata_repository.load_version()
        return data.get("pending_version")

    def create_pending_version(self, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Create a pending version (increment but not published).
        Returns new pending version number.
        """
        data = self._metadata_repository.load_version()
        current = data.get("platform_version", 1)
        new_version = current + 1
        data["pending_version"] = new_version
        if metadata:
            data.update(metadata)
        self._metadata_repository.save_version(data)
        logger.info(f"Pending version created: {new_version} (current published: {current})")
        return new_version

    def publish_pending_version(self) -> bool:
        """
        Publish the pending version: move pending_version to platform_version.
        Returns True if successful.
        """
        data = self._metadata_repository.load_version()
        pending = data.get("pending_version")
        if pending is None:
            logger.warning("No pending version to publish")
            return False
        data["platform_version"] = pending
        del data["pending_version"]
        self._metadata_repository.save_version(data)
        logger.info(f"Pending version {pending} published as platform_version")
        return True

    def clear_pending_version(self) -> None:
        """Clear pending version (e.g., after rollback)."""
        data = self._metadata_repository.load_version()
        if "pending_version" in data:
            del data["pending_version"]
            self._metadata_repository.save_version(data)
            logger.info("Pending version cleared")

    def increment_version(self, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Deprecated: use create_pending_version() + publish_pending_version()."""
        return self.create_pending_version(metadata)

    def update_repository_manifest(self, repo_path: Path, version: int) -> bool:
        """
        Update manifest.json in repository with new version.
        This is called BEFORE Git commit.
        """
        try:
            manifest_path = repo_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {
                    "schema_version": 1,
                    "runtime_version": 0,
                    "database_version": 1,
                    "minimum_app_version": "0.1.0",
                    "publisher": "CenterManager",
                    "branch": "main",
                    "created_at": datetime.now().isoformat(),
                    "published_at": None,
                }

            data["runtime_version"] = version
            data["published_at"] = datetime.now().isoformat()
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"Repository manifest updated to version {version}")
            return True
        except Exception as e:
            logger.exception(f"Failed to update repository manifest: {e}")
            return False

    def update_manifest_version(self, new_version: int, repo_path: Path) -> bool:
        """Update manifest.json in repository with new version."""
        try:
            runtime_manifest_path = get_paths().runtime_root / "manifest.json"
            self._update_manifest_file(runtime_manifest_path, new_version)

            repo_manifest_path = repo_path / "manifest.json"
            self._update_manifest_file(repo_manifest_path, new_version)

            logger.info(f"Manifest updated to version {new_version} in both runtime and repository")
            return True
        except Exception as e:
            logger.exception(f"Failed to update manifest: {e}")
            return False

    def _update_manifest_file(self, path: Path, version: int) -> None:
        """Update a single manifest file with new version."""
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "schema_version": 1,
                "runtime_version": 0,
                "database_version": 1,
                "minimum_app_version": "0.1.0",
                "publisher": "CenterManager",
                "branch": "main",
                "created_at": datetime.now().isoformat(),
                "published_at": None,
            }

        data["runtime_version"] = version
        data["published_at"] = datetime.now().isoformat()

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def refresh(self) -> bool:
        """Reload version from repository. Returns True if version changed."""
        old = self.get_current_version()
        self._version_cache = None
        new = self.get_current_version()
        return new != old   