# -*- coding: utf-8 -*-
"""E2E tests for two-machine sync (simulated)."""

import pytest
import shutil
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime

from centermanager.core.paths import Paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.synchronization import GitSynchronizationProvider, SynchronizationManager
from centermanager.platform.version import VersionManager
from centermanager.events.event_bus import EventBus
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def temp_repo(tmp_path):
    """Create a bare repository to use as remote."""
    repo_path = tmp_path / "remote.git"
    repo_path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--bare"], cwd=repo_path, capture_output=True)
    return repo_path


def create_runtime_env(tmp_path, remote_repo, label):
    """Create a local repository with initial commit and push to remote."""
    root = tmp_path / f"runtime_{label}"
    root.mkdir(parents=True, exist_ok=True)
    db_dir = root / "Database"
    db_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = root / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    collab_dir = root / "collaboration"
    collab_dir.mkdir(parents=True, exist_ok=True)

    # Create local repository (not clone)
    repo_dst = root / "repository"
    repo_dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_dst, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dst, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dst, capture_output=True)

    # Create manifest
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
    with open(repo_dst / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    with open(root / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    with open(meta_dir / "version.json", "w") as f:
        json.dump({"platform_version": 1}, f)

    # Commit and push to remote using as_uri to handle spaces in path
    subprocess.run(["git", "add", "."], cwd=repo_dst, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dst, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", remote_repo.as_uri()], cwd=repo_dst, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=repo_dst, capture_output=True)

    # Create a class for paths
    class TestPaths:
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

    return TestPaths(root), repo_dst


def test_two_machine_sync(temp_repo, tmp_path):
    """Simulate two machines syncing via Git."""
    remote_repo = temp_repo  # bare repository
    remote_url = remote_repo.as_uri()  # file:/// URL with spaces encoded

    # Machine A
    paths_a, repo_a = create_runtime_env(tmp_path, remote_repo, "A")
    # Machine B
    paths_b, repo_b = create_runtime_env(tmp_path, remote_repo, "B")

    # Initialize both machines' services
    event_bus = EventBus()

    # Machine A setup
    cm_a = CollaborationManager(runtime_root=paths_a.runtime_root, event_bus=event_bus)
    cm_a.initialize("user_a", "user_a", "admin")

    provider_a = GitSynchronizationProvider(
        repo_path=repo_a,
        repository_url=remote_url,
        token="",
        branch="main"
    )
    provider_a.connect()

    sync_manager_a = SynchronizationManager(provider_a, event_bus=event_bus)
    sync_service_a = RuntimeSyncService(
        sync_manager=sync_manager_a,
        collab_manager=cm_a,
        context_manager=None,
        event_bus=event_bus,
        poll_interval=1
    )
    sync_service_a.start()

    # Machine B setup
    cm_b = CollaborationManager(runtime_root=paths_b.runtime_root, event_bus=event_bus)
    cm_b.initialize("user_b", "user_b", "admin")

    provider_b = GitSynchronizationProvider(
        repo_path=repo_b,
        repository_url=remote_url,
        token="",
        branch="main"
    )
    provider_b.connect()

    sync_manager_b = SynchronizationManager(provider_b, event_bus=event_bus)
    sync_service_b = RuntimeSyncService(
        sync_manager=sync_manager_b,
        collab_manager=cm_b,
        context_manager=None,
        event_bus=event_bus,
        poll_interval=1
    )
    sync_service_b.start()

    # Create initial database on A with student
    db_a = paths_a.database_dir / "center.db"
    engine_a = create_engine_for_path(db_a)
    Base.metadata.create_all(engine_a)
    Session_a = sessionmaker(bind=engine_a)
    with Session_a() as session:
        student = Student(student_code="HS001", full_name="Student A")
        session.add(student)
        session.commit()

    # Copy DB to repository and publish on A
    repo_db_a = repo_a / "database"
    repo_db_a.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_a, repo_db_a / "center.db")
    provider_a.publish("Initial data", "user_a")

    # Force B to pull immediately
    sync_service_b.check_for_updates()
    sync_service_b.execute_sync()

    # Check B's database
    db_b = paths_b.database_dir / "center.db"
    assert db_b.exists()
    engine_b = create_engine_for_path(db_b)
    Session_b = sessionmaker(bind=engine_b)
    with Session_b() as session:
        students = session.query(Student).all()
        assert len(students) == 1
        assert students[0].full_name == "Student A"

    # Now modify on B
    with Session_b() as session:
        student = session.query(Student).first()
        student.full_name = "Student B"
        session.commit()

    # Copy B's DB to repo and publish
    repo_db_b = repo_b / "database"
    repo_db_b.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_b, repo_db_b / "center.db")
    provider_b.publish("Update from B", "user_b")

    # Force A to pull
    sync_service_a.check_for_updates()
    sync_service_a.execute_sync()

    # Check A's database
    with Session_a() as session:
        students = session.query(Student).all()
        assert len(students) == 1
        assert students[0].full_name == "Student B"

    # Cleanup
    sync_service_a.stop()
    sync_service_b.stop()