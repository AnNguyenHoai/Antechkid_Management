# -*- coding: utf-8 -*-
"""
Pytest fixtures for CenterManager tests.
"""
import pytest
import shutil
import logging
import sys
from pathlib import Path

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