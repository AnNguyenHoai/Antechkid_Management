# -*- coding: utf-8 -*-
"""RuntimeValidator - Validate runtime directory structure."""

import logging
from pathlib import Path
from typing import List, Optional

from .exceptions import RuntimeValidationFailedError

logger = logging.getLogger(__name__)

REQUIRED_DIRS = [
    "database",
    "metadata",
    "reports",
    "attachments",
    "collaboration",
]


class RuntimeValidator:
    """Validate runtime directory structure."""

    def __init__(self, runtime_root: Path):
        self._runtime_root = runtime_root

    def validate(self, raise_on_error: bool = False) -> bool:
        """
        Validate runtime structure.
        Returns True if valid, False otherwise.
        If raise_on_error is True, raises RuntimeValidationFailedError.
        """
        missing = []
        for dir_name in REQUIRED_DIRS:
            dir_path = self._runtime_root / dir_name
            if not dir_path.exists():
                missing.append(dir_name)
                logger.warning(f"Missing directory: {dir_path}")

        # Check database file (optional in early boot)
        db_path = self._runtime_root / "database" / "center.db"
        if not db_path.exists():
            logger.warning(f"Database file not found: {db_path}")

        if missing:
            if raise_on_error:
                raise RuntimeValidationFailedError(
                    f"Runtime validation failed. Missing directories: {', '.join(missing)}"
                )
            return False

        logger.info(f"Runtime validation passed: {self._runtime_root}")
        return True

    def get_missing_dirs(self) -> List[str]:
        """Get list of missing required directories."""
        missing = []
        for dir_name in REQUIRED_DIRS:
            if not (self._runtime_root / dir_name).exists():
                missing.append(dir_name)
        return missing