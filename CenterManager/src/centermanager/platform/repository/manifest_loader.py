# -*- coding: utf-8 -*-
"""ManifestLoader - Load and validate runtime manifest.json."""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from .exceptions import ManifestNotFoundError, ManifestInvalidError

logger = logging.getLogger(__name__)

# Required fields and their types
REQUIRED_FIELDS = {
    "schema_version": int,
    "runtime_version": int,
    "database_version": int,
    "minimum_app_version": str,
    "publisher": str,
    "branch": str,
    "created_at": str,
    "published_at": (str, type(None)),  # can be null
}


class ManifestLoader:
    """Load and validate runtime manifest.json."""

    def __init__(self, manifest_path: Path):
        self._manifest_path = manifest_path

    def exists(self) -> bool:
        """Check if manifest file exists."""
        return self._manifest_path.exists()

    def load(self) -> Dict[str, Any]:
        """
        Load manifest from disk.
        Raises ManifestNotFoundError if missing.
        Raises ManifestInvalidError if invalid.
        """
        if not self.exists():
            raise ManifestNotFoundError(f"Manifest not found: {self._manifest_path}")

        try:
            with open(self._manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ManifestInvalidError(f"Invalid JSON in manifest: {e}")

        # Validate required fields
        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in data:
                raise ManifestInvalidError(f"Missing required field: {field}")
            if field == "published_at":
                if data[field] is not None and not isinstance(data[field], str):
                    raise ManifestInvalidError(f"Field '{field}' must be string or null")
            elif not isinstance(data[field], expected_type):
                raise ManifestInvalidError(
                    f"Field '{field}' has wrong type. Expected {expected_type.__name__}, got {type(data[field]).__name__}"
                )

        # Validate schema version
        if data["schema_version"] != 1:
            raise ManifestInvalidError(f"Unsupported schema version: {data['schema_version']}")

        logger.info(f"Manifest loaded: version {data['runtime_version']}")
        return data

    def get_version(self) -> int:
        """Load and return runtime_version."""
        data = self.load()
        return data.get("runtime_version", 0)