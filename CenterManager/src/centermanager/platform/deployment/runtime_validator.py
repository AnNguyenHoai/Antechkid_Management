# -*- coding: utf-8 -*-
"""Runtime validation for deployment."""

import logging
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from centermanager.core.paths import get_paths
from centermanager.platform.deployment.repository_manager import RepositoryManager
from centermanager.platform.deployment.deployment_config import DeploymentConfig

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass
class ValidationResult:
    severity: ValidationSeverity
    message: str
    details: List[str]


class RuntimeValidator:
    """Validate runtime environment and repository."""

    def __init__(self) -> None:
        self._paths = get_paths()
        self._deployment_config = DeploymentConfig()
        self._repo_manager = RepositoryManager()

    def validate_all(self) -> ValidationResult:
        """Run all validations and return aggregated result."""
        errors = []
        warnings = []

        # 1. Check runtime directories exist
        dirs = [
            self._paths.database_dir,
            self._paths.metadata_dir,
            self._paths.config_dir,
            self._paths.logs_dir,
            self._paths.backup_dir,
            self._paths.reports_dir,
        ]
        for d in dirs:
            if not d.exists():
                errors.append(f"Missing runtime directory: {d}")

        # 2. Check database file
        db_path = self._paths.database_dir / "center.db"
        if not db_path.exists():
            errors.append(f"Database file not found: {db_path}")

        # 3. Check metadata files
        metadata_files = ["lock.json", "version.json", "deployment.json"]
        meta_dir = self._paths.metadata_dir
        for fname in metadata_files:
            f = meta_dir / fname
            if not f.exists():
                errors.append(f"Missing metadata file: {f}")

        # 4. Check repository existence and validity
        repo_path = self._deployment_config.get_local_path()
        if not repo_path.exists():
            errors.append(f"Repository not found at: {repo_path}")
        elif not (repo_path / ".git").exists():
            errors.append(f"Repository missing .git directory: {repo_path}")
        else:
            # Validate repository using RepositoryManager
            try:
                if not self._repo_manager.is_valid():
                    errors.append("Repository is invalid (missing required files or corrupted).")
                else:
                    # Check if repository contains database and metadata
                    repo_db = repo_path / "database" / "center.db"
                    if not repo_db.exists():
                        warnings.append("Repository does not contain database/center.db (may need sync).")
            except Exception as e:
                errors.append(f"Repository validation error: {e}")

        # 5. Check config.json exists
        config_file = self._paths.config_file
        if not config_file.exists():
            errors.append(f"Config file not found: {config_file}")

        # 6. Check Git executable is available
        from centermanager.platform.deployment.git_locator import locate_git
        git_path = locate_git()
        if git_path is None:
            warnings.append("No Git executable found. Please install Git or provide portable Git.")

        # Determine overall severity
        if errors:
            severity = ValidationSeverity.ERROR
            message = f"{len(errors)} error(s) found."
        elif warnings:
            severity = ValidationSeverity.WARNING
            message = f"{len(warnings)} warning(s) found."
        else:
            severity = ValidationSeverity.HEALTHY
            message = "All validations passed."

        return ValidationResult(
            severity=severity,
            message=message,
            details=errors + warnings,
        )

    def is_healthy(self) -> bool:
        """Convenience method to check if runtime is fully healthy."""
        result = self.validate_all()
        return result.severity == ValidationSeverity.HEALTHY

    def can_attempt_deployment(self) -> bool:
        """Check if we have enough information to attempt deployment."""
        # At least repository URL and token must be configured
        config = DeploymentConfig()
        return bool(config.get_repository_url() and config.get_token())