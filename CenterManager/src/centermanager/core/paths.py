# -*- coding: utf-8 -*-
"""
Centralized path resolution for CenterManager.
"""
from pathlib import Path
from typing import Optional


class Paths:
    def __init__(self) -> None:
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

    @property
    def reports_dir(self) -> Path:
        return self._runtime_root / "Reports"

    @property
    def temp_dir(self) -> Path:
        return self._runtime_root / "Temp"

    @property
    def metadata_dir(self) -> Path:
        return self._runtime_root / "metadata"

    def ensure_directories(self) -> None:
        dirs = [
            self.database_dir,
            self.export_dir,
            self.student_profile_dir,
            self.excel_export_dir,
            self.attachment_dir,
            self.config_dir,
            self.backup_dir,
            self.logs_dir,
            self.reports_dir,
            self.temp_dir,
            self.metadata_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


_paths: Optional[Paths] = None

def get_paths() -> Paths:
    global _paths
    if _paths is None:
        _paths = Paths()
    return _paths


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

def reports_dir() -> Path:
    return get_paths().reports_dir

def temp_dir() -> Path:
    return get_paths().temp_dir

def metadata_dir() -> Path:
    return get_paths().metadata_dir