# tests/test_remote_detection.py
# -*- coding: utf-8 -*-
"""Tests for remote version detection."""

import pytest
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime

from centermanager.core.paths import Paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.platform.synchronization import GitSynchronizationProvider, SynchronizationManager, SyncResult
from centermanager.events.event_bus import EventBus
from sqlalchemy.orm import sessionmaker


def create_seeded_remote(tmp_path):
    """Create a seeded bare remote with manifest version 1."""
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, capture_output=True, check=True)

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

    # Verify manifest.json tồn tại
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
def runtime_env(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    db_dir = root / "Database"
    db_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = root / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)

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
    with open(root / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    with open(meta_dir / "version.json", "w") as f:
        json.dump({"platform_version": 1}, f)

    class TestPaths(Paths):
        def __init__(self, r):
            self._runtime_root = r
            self._project_root = r.parent
        @property
        def runtime_root(self):
            return self._runtime_root
        @property
        def database_dir(self):
            return self._runtime_root / "Database"
        @property
        def metadata_dir(self):
            return self._runtime_root / "metadata"
        @property
        def config_dir(self):
            return self._runtime_root / "Config"
        @property
        def logs_dir(self):
            return self._runtime_root / "Logs"
        @property
        def backup_dir(self):
            return self._runtime_root / "Backup"
        @property
        def attachment_dir(self):
            return self._runtime_root / "Attachment"
        @property
        def reports_dir(self):
            return self._runtime_root / "Reports"
        @property
        def export_dir(self):
            return self._runtime_root / "Export"
        def ensure_directories(self):
            for d in [self.database_dir, self.metadata_dir, self.config_dir,
                      self.logs_dir, self.backup_dir, self.attachment_dir,
                      self.reports_dir, self.export_dir]:
                d.mkdir(parents=True, exist_ok=True)

    test_paths = TestPaths(root)
    import centermanager.core.paths as paths_mod
    paths_mod._paths = test_paths

    yield test_paths

    paths_mod._paths = None


def test_remote_detection_after_publish(runtime_env, tmp_path):
    """Test that remote version is detected correctly after publish."""
    # Create a fresh seeded remote for this test
    remote_path = create_seeded_remote(tmp_path)

    # Create database with student
    db_path = runtime_env.database_dir / "center.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        student = Student(student_code="HS001", full_name="Student A")
        session.add(student)
        session.commit()

    # Setup provider - clone from freshly created remote
    repo_path = runtime_env.runtime_root / "repository"
    if repo_path.exists():
        shutil.rmtree(repo_path)

    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=remote_path.as_uri(),
        token="",
        branch="main"
    )
    provider.connect()
    provider.clone()

    # Verify initial current_version
    current = provider.current_version()
    assert current == 1, f"Expected 1, got {current}"

    # Update manifest to version 2 in repository
    manifest_path = repo_path / "manifest.json"
    assert manifest_path.exists()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["runtime_version"] = 2
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # Verify current_version after update (before commit)
    assert provider.current_version() == 2

    # Add and commit
    subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Update to version 2"], cwd=repo_path, capture_output=True, check=True)
    subprocess.run(["git", "push", "origin", "main"], cwd=repo_path, capture_output=True, check=True)

    # Verify current_version after push (should still be 2)
    assert provider.current_version() == 2

    # Setup sync manager
    event_bus = EventBus()
    sync_manager = SynchronizationManager(provider, event_bus=event_bus)

    # Check updates (will fetch remote)
    result = sync_manager.check_updates()

    # Assert remote version detected
    assert result.current_version == 2, f"Expected current_version=2, got {result.current_version}"
    assert result.remote_version == 2, f"Expected remote_version=2, got {result.remote_version}"
    assert result.result == SyncResult.NO_CHANGE