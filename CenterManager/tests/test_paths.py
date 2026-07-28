# -*- coding: utf-8 -*-
"""
Tests for path resolution.
"""
import pytest
from pathlib import Path
import shutil

from centermanager.core.paths import (
    get_paths,
    project_root,
    runtime_root,
    database_dir,
    export_dir,
    student_profile_dir,
    excel_export_dir,
    attachment_dir,
    config_dir,
    config_file,
    backup_dir,
    logs_dir,
)


def test_paths_singleton(clean_paths):
    """Test that get_paths returns a singleton."""
    p1 = get_paths()
    p2 = get_paths()
    assert p1 is p2


def test_project_root_resolution(clean_paths):
    """Test that project_root resolves to the correct directory."""
    root = project_root()
    # run.py always exists at project root
    assert (root / "run.py").exists()


def test_runtime_root(clean_paths):
    """Test that runtime_root is under project_root."""
    root = runtime_root()
    assert root == project_root() / "runtime"


def test_database_dir(clean_paths):
    """Test database_dir location."""
    assert database_dir() == runtime_root() / "Database"


def test_export_dir(clean_paths):
    """Test export_dir location."""
    assert export_dir() == runtime_root() / "Export"


def test_student_profile_dir(clean_paths):
    """Test student_profile_dir location."""
    assert student_profile_dir() == export_dir() / "StudentProfile"


def test_excel_export_dir(clean_paths):
    """Test excel_export_dir location."""
    assert excel_export_dir() == export_dir() / "Excel"


def test_attachment_dir(clean_paths):
    """Test attachment_dir location."""
    assert attachment_dir() == runtime_root() / "Attachment"


def test_config_dir(clean_paths):
    """Test config_dir location."""
    assert config_dir() == runtime_root() / "Config"


def test_config_file(clean_paths):
    """Test config_file location."""
    assert config_file() == config_dir() / "config.json"


def test_backup_dir(clean_paths):
    """Test backup_dir location."""
    assert backup_dir() == runtime_root() / "Backup"


def test_logs_dir(clean_paths):
    """Test logs_dir location."""
    assert logs_dir() == runtime_root() / "Logs"


# Các test khác giữ nguyên clean_paths, chỉ đổi test này
def test_ensure_directories_creates_all(temp_runtime):
    """Test that ensure_directories creates all required directories."""
    paths = get_paths()
    # Remove temp runtime dir if exists (safe because it's temp)
    if paths.runtime_root.exists():
        shutil.rmtree(paths.runtime_root)
    assert not paths.runtime_root.exists()
    paths.ensure_directories()
    assert paths.database_dir.exists()
    assert paths.export_dir.exists()
    assert paths.student_profile_dir.exists()
    assert paths.excel_export_dir.exists()
    assert paths.attachment_dir.exists()
    assert paths.config_dir.exists()
    assert paths.backup_dir.exists()
    assert paths.logs_dir.exists()