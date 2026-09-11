# -*- coding: utf-8 -*-
"""E2E tests for two-machine sync (simulated)."""

import sys
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


# Skip on Windows due to path space issues
@pytest.mark.skipif(sys.platform == "win32", reason="Windows path spaces cause Git errors")
def test_two_machine_sync(temp_repo, tmp_path):
    """Simulate two machines syncing via Git."""
    remote_repo = temp_repo

    # Initialize remote with initial content
    initialize_remote(remote_repo)

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
        repository_url=remote_repo.as_uri(),
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
        repository_url=remote_repo.as_uri(),
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