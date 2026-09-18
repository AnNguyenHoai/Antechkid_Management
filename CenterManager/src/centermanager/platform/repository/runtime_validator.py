# -*- coding: utf-8 -*-
"""RuntimeValidator - Validate the canonical application runtime structure."""

import logging
from pathlib import Path
from typing import List

from centermanager.core.paths import RUNTIME_REQUIRED_DIRS
from .exceptions import RuntimeValidationFailedError

logger = logging.getLogger(__name__)

class RuntimeValidator:
    """Validate the canonical runtime directory contract."""

    def __init__(self, runtime_root: Path):
        self._runtime_root = runtime_root

    def validate(self, raise_on_error: bool = False) -> bool:
        """Return True only when every required runtime directory exists."""
        missing = self.get_missing_dirs()
        for dir_name in missing:
            logger.warning("Missing runtime directory: %s", self._runtime_root / dir_name)

        # The database file is intentionally optional during early bootstrap;
        # migrations create it after the runtime directory contract is ready.
        db_path = self._runtime_root / "Database" / "center.db"
        if not db_path.exists():
            logger.warning("Database file not found (allowed during bootstrap): %s", db_path)

        if missing:
            if raise_on_error:
                raise RuntimeValidationFailedError(
                    "Runtime validation failed. Missing directories: "
                    + ", ".join(missing)
                )
            return False

        logger.info("Runtime validation passed: %s", self._runtime_root)
        return True

    def get_missing_dirs(self) -> List[str]:
        """Return canonical runtime directories that are missing."""
        return [
            dir_name
            for dir_name in RUNTIME_REQUIRED_DIRS
            if not (self._runtime_root / dir_name).is_dir()
        ]
