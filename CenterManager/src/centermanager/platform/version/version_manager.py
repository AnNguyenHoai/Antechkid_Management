# -*- coding: utf-8 -*-
"""
Version Manager - manages platform version.
"""
import logging
from typing import Dict, Any, Optional

from centermanager.platform.collaboration.metadata_repository import MetadataRepository
from centermanager.events.event_bus import EventBus

logger = logging.getLogger(__name__)


class VersionManager:
    def __init__(self, metadata_repository: MetadataRepository, event_bus: EventBus):
        self._metadata_repository = metadata_repository
        self._event_bus = event_bus
        self._version_cache = None

    def get_current_version(self) -> int:
        """Get current platform version."""
        data = self._metadata_repository.load_version()
        return data.get("platform_version", 1)

    def increment_version(self, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Increment platform version and save to metadata.
        Returns new version number.
        """
        data = self._metadata_repository.load_version()
        current = data.get("platform_version", 1)
        new_version = current + 1
        data["platform_version"] = new_version
        if metadata:
            data.update(metadata)
        self._metadata_repository.save_version(data)
        logger.info(f"Version incremented: {current} -> {new_version}")
        return new_version

    def refresh(self) -> bool:
        """Reload version from repository. Returns True if version changed."""
        old = self.get_current_version()
        self._version_cache = None
        new = self.get_current_version()
        return new != old