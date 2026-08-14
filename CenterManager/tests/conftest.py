# tests/conftest.py
# -*- coding: utf-8 -*-
"""Pytest fixtures for CenterManager tests."""

import pytest
import subprocess
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Thêm src/ vào sys.path để pytest tìm thấy centermanager
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.core import paths as paths_module
from centermanager.core import config as config_module
from centermanager.core.paths import get_paths

# Lưu đường dẫn runtime thật để kiểm tra bảo vệ
REAL_RUNTIME_PATH = get_paths().runtime_root


@pytest.fixture
def clean_paths():
    """Reset path and config state."""
    old_paths = paths_module._paths
    old_config = config_module._config
    paths_module._paths = None
    config_module._config = None
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    yield
    paths_module._paths = old_paths
    config_module._config = old_config


@pytest.fixture
def temp_runtime(tmp_path, clean_paths):
    """Create temporary runtime directory."""
    from centermanager.core import paths as pmod
    from centermanager.core import config as cmod

    class TempPaths:
        def __init__(self, root):
            self._root = root
        @property
        def project_root(self): return self._root
        @property
        def runtime_root(self): return self._root / "runtime"
        @property
        def database_dir(self): return self.runtime_root / "Database"
        @property
        def export_dir(self): return self.runtime_root / "Export"
        @property
        def student_profile_dir(self): return self.export_dir / "StudentProfile"
        @property
        def excel_export_dir(self): return self.export_dir / "Excel"
        @property
        def attachment_dir(self): return self.runtime_root / "Attachment"
        @property
        def config_dir(self): return self.runtime_root / "Config"
        @property
        def config_file(self): return self.config_dir / "config.json"
        @property
        def backup_dir(self): return self.runtime_root / "Backup"
        @property
        def logs_dir(self): return self.runtime_root / "Logs"
        def ensure_directories(self):
            for d in [self.database_dir, self.export_dir, self.student_profile_dir,
                      self.excel_export_dir, self.attachment_dir, self.config_dir,
                      self.backup_dir, self.logs_dir]:
                d.mkdir(parents=True, exist_ok=True)

    temp_paths = TempPaths(tmp_path)
    pmod._paths = temp_paths
    cmod._config = None

    yield temp_paths

    pmod._paths = None
    cmod._config = None


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database path for testing."""
    db_path = tmp_path / "test.db"
    return db_path


@pytest.fixture
def test_db(test_db_path):
    """Create a temporary database with initialized tables."""
    from centermanager.database.engine import create_engine_for_path
    from centermanager.database.base import Base
    from centermanager import models  # noqa

    engine = create_engine_for_path(test_db_path)
    Base.metadata.create_all(engine)
    yield test_db_path


@pytest.fixture(scope="session")
def seeded_center_manager_remote(tmp_path_factory):
    """
    Tạo bare remote repository với cấu trúc CenterManager tối thiểu.
    Phù hợp cho các test cần clone và publish.
    """
    tmp_path = tmp_path_factory.mktemp("seeded_remote")
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, capture_output=True, check=True)

    # Tạo source repo để seed
    source_path = tmp_path / "source"
    source_path.mkdir()
    subprocess.run(["git", "init"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source_path, capture_output=True, check=True)

    # Tạo nội dung cần thiết
    (source_path / "README.md").write_text("# CenterManager Test Repository")
    manifest = {
        "schema_version": 1,
        "runtime_version": 1,
        "database_version": 1,
        "minimum_app_version": "0.1.0",
        "publisher": "Test",
        "branch": "main",
        "created_at": datetime.now().isoformat(),
        "published_at": None,
    }
    with open(source_path / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Đảm bảo branch là 'main'
    result = subprocess.run(["git", "branch", "--show-current"], cwd=source_path, capture_output=True, text=True)
    current_branch = result.stdout.strip()
    if current_branch != "main":
        subprocess.run(["git", "branch", "-m", current_branch, "main"], cwd=source_path, capture_output=True, check=True)

    subprocess.run(["git", "add", "."], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial CenterManager structure"], cwd=source_path, capture_output=True, check=True)

    # Push main lên bare remote
    subprocess.run(["git", "push", str(remote_path), "main"], cwd=source_path, capture_output=True, check=True)

    # Verify remote có refs/heads/main
    result = subprocess.run(
        ["git", "--git-dir", str(remote_path), "show-ref", "refs/heads/main"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError("Remote does not have refs/heads/main")

    # Verify manifest.json tồn tại trong remote
    show_ref_out = subprocess.run(
        ["git", "--git-dir", str(remote_path), "show-ref", "refs/heads/main"],
        capture_output=True, text=True, check=True
    )
    commit_hash = show_ref_out.stdout.split()[0]
    ls_tree = subprocess.run(
        ["git", "--git-dir", str(remote_path), "ls-tree", commit_hash],
        capture_output=True, text=True, check=True
    )
    if "manifest.json" not in ls_tree.stdout:
        raise RuntimeError("manifest.json not found in initial commit")

    return remote_path

@pytest.fixture
def fresh_center_manager_remote(tmp_path):
    """
    Tạo bare remote repository với cấu trúc CenterManager tối thiểu.
    Scope function để mỗi test có remote riêng, không bị ảnh hưởng bởi test khác.
    """
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, capture_output=True, check=True)

    source_path = tmp_path / "source"
    source_path.mkdir()
    subprocess.run(["git", "init"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source_path, capture_output=True, check=True)

    (source_path / "README.md").write_text("# CenterManager Test Repository")
    manifest = {
        "schema_version": 1,
        "runtime_version": 1,
        "database_version": 1,
        "minimum_app_version": "0.1.0",
        "publisher": "Test",
        "branch": "main",
        "created_at": datetime.now().isoformat(),
        "published_at": None,
    }
    with open(source_path / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    result = subprocess.run(["git", "branch", "--show-current"], cwd=source_path, capture_output=True, text=True)
    current_branch = result.stdout.strip()
    if current_branch != "main":
        subprocess.run(["git", "branch", "-m", current_branch, "main"], cwd=source_path, capture_output=True, check=True)

    subprocess.run(["git", "add", "."], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial CenterManager structure"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "push", str(remote_path), "main"], cwd=source_path, capture_output=True, check=True)

    result = subprocess.run(
        ["git", "--git-dir", str(remote_path), "show-ref", "refs/heads/main"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError("Remote does not have refs/heads/main")

    return remote_path