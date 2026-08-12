# -*- coding: utf-8 -*-
"""RepositoryManager - Manage Runtime Repository (local only)."""

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from centermanager.core.paths import get_paths
from .repository_state import RepositoryState
from .manifest_loader import ManifestLoader
from .runtime_validator import RuntimeValidator
from .exceptions import (
    RepositoryNotFoundError,
    ManifestNotFoundError,
    ManifestInvalidError,
    RuntimeValidationFailedError,
)

logger = logging.getLogger(__name__)


class RepositoryManager:
    """
    Manages local Runtime Repository.
    Read-only state inspection.
    No Git, no synchronization.
    """

    def __init__(self, runtime_root: Optional[Path] = None):
        self._runtime_root = runtime_root or get_paths().runtime_root
        self._manifest_path = self._runtime_root / "manifest.json"
        self._loader = ManifestLoader(self._manifest_path)
        self._validator = RuntimeValidator(self._runtime_root)
        self._cached_state: Optional[RepositoryState] = None
        self._cached_manifest: Optional[Dict[str, Any]] = None

    def detect(self) -> RepositoryState:
        """Detect repository state."""
        # Check repository root exists
        if not self._runtime_root.exists():
            return RepositoryState.NOT_FOUND

        # Check manifest exists
        if not self._loader.exists():
            return RepositoryState.INVALID

        # Try to load manifest
        try:
            manifest = self._loader.load()
            self._cached_manifest = manifest
        except ManifestInvalidError:
            return RepositoryState.CORRUPTED
        except Exception:
            return RepositoryState.CORRUPTED

        # Validate runtime structure
        if not self._validator.validate(raise_on_error=False):
            return RepositoryState.INVALID

        # Check if offline? (not yet implemented)
        # For now, assume online if repository exists and validated.
        return RepositoryState.READY

    def state(self, force_refresh: bool = False) -> RepositoryState:
        """Get repository state. Uses cache unless force_refresh=True."""
        if self._cached_state is None or force_refresh:
            self._cached_state = self.detect()
        return self._cached_state

    def validate(self) -> bool:
        """Validate repository. Returns True if valid."""
        return self.state() == RepositoryState.READY

    def manifest(self) -> Optional[Dict[str, Any]]:
        """Get cached manifest. Loads if not cached."""
        if self._cached_manifest is None:
            try:
                self._cached_manifest = self._loader.load()
            except Exception:
                return None
        return self._cached_manifest

    def refresh(self) -> None:
        """Force refresh state and manifest."""
        self._cached_state = None
        self._cached_manifest = None
        self.state(force_refresh=True)

    def runtime_root(self) -> Path:
        """Get runtime root path."""
        return self._runtime_root