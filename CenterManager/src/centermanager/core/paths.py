# -*- coding: utf-8 -*-
"""
Centralized path resolution for CenterManager.

All runtime paths are derived from the project root and resolved
using pathlib. No hardcoded absolute paths are used.
"""
from pathlib import Path
from typing import Optional


class Paths:
    """
    Container for all application paths.

    Attributes:
        project_root: Root directory of the project (parent of src/).
        runtime_root: Runtime directory (project_root / 'runtime').
    """

    def __init__(self) -> None:
        # Project root = parent of 'src' directory
        # paths.py is in src/centermanager/core/
        self._project_root = Path(__file__).resolve().parent.parent.parent.parent
        self._runtime_root = self._project_root / "runtime"

    @property
    def project_root(self) -> Path:
        return self._project_root

    @property
    def runtime_root(self) -> Path:
        return self._runtime_root

    @property
    def database_dir(self) -> Path:
        return self._runtime_root / "Database"

    @property
    def export_dir(self) -> Path:
        return self._runtime_root / "Export"

    @property
    def student_profile_dir(self) -> Path:
        return self.export_dir / "StudentProfile"

    @property
    def excel_export_dir(self) -> Path:
        return self.export_dir / "Excel"

    @property
    def attachment_dir(self) -> Path:
        return self._runtime_root / "Attachment"

    @property
    def config_dir(self) -> Path:
        return self._runtime_root / "Config"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def backup_dir(self) -> Path:
        return self._runtime_root / "Backup"

    @property
    def logs_dir(self) -> Path:
        return self._runtime_root / "Logs"

    def ensure_directories(self) -> None:
        """
        Create all required runtime directories if they do not exist.
        """
        dirs = [
            self.database_dir,
            self.export_dir,
            self.student_profile_dir,
            self.excel_export_dir,
            self.attachment_dir,
            self.config_dir,
            self.backup_dir,
            self.logs_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


# Singleton instance
_paths: Optional[Paths] = None


def get_paths() -> Paths:
    """Get the global Paths singleton."""
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths


# Convenience functions for direct import
def project_root() -> Path:
    return get_paths().project_root


def runtime_root() -> Path:
    return get_paths().runtime_root


def database_dir() -> Path:
    return get_paths().database_dir


def export_dir() -> Path:
    return get_paths().export_dir


def student_profile_dir() -> Path:
    return get_paths().student_profile_dir


def excel_export_dir() -> Path:
    return get_paths().excel_export_dir


def attachment_dir() -> Path:
    return get_paths().attachment_dir


def config_dir() -> Path:
    return get_paths().config_dir


def config_file() -> Path:
    return get_paths().config_file


def backup_dir() -> Path:
    return get_paths().backup_dir


def logs_dir() -> Path:
    return get_paths().logs_dir