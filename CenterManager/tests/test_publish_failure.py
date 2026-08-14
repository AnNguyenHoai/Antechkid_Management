# tests/test_publish_failure.py
# -*- coding: utf-8 -*-
"""Tests for publish failure and retry semantics."""

import pytest
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

from centermanager.core.paths import Paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.platform.version import VersionManager
from centermanager.events.event_bus import EventBus
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def runtime_env(seeded_center_manager_remote, tmp_path):
    root = tmp_path / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    db_dir = root / "Database"
    db_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = root / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    collab_dir = root / "collaboration"
    collab_dir.mkdir(parents=True, exist_ok=True)

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


def test_publish_failure_retry(runtime_env, seeded_center_manager_remote):
    """Test that publish failure keeps lock and pending version, and retry succeeds."""
    # Create database with a student
    db_path = runtime_env.database_dir / "center.db"
    engine = create_engine_for_path(db_path)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        student = Student(student_code="HS001", full_name="Test Student")
        session.add(student)
        session.commit()

    # Setup collaboration
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=runtime_env.runtime_root, event_bus=event_bus)
    cm.initialize("test_user", "test_user", "admin")

    # Setup version manager
    from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
    meta_repo = JsonMetadataRepository(runtime_env.metadata_dir)
    version_manager = VersionManager(meta_repo, event_bus)

    # Setup sync provider - clone from seeded remote
    repo_path = runtime_env.runtime_root / "repository"
    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=seeded_center_manager_remote.as_uri(),
        token="",
        branch="main"
    )
    provider.connect()
    if not repo_path.exists():
        provider.clone()

    # Setup sync service and transaction
    from centermanager.platform.synchronization import SynchronizationManager
    sync_manager = SynchronizationManager(provider, event_bus=event_bus)
    sync_service = RuntimeSyncService(
        sync_manager=sync_manager,
        collab_manager=cm,
        context_manager=None,
        event_bus=event_bus,
        poll_interval=30
    )

    tx = WriteTransactionManager(cm)
    tx.set_sync_service(sync_service)
    tx.set_version_manager(version_manager)

    # Start editing
    def save_local():
        with Session() as sess:
            s = sess.query(Student).first()
            s.full_name = "Updated Student"
            sess.commit()
        return True

    tx.start_editing(save_local)
    tx.mark_dirty()

    # Mock _do_publish: first call fails, second call calls original
    call_count = 0
    original_do_publish = tx._do_publish

    def mock_do_publish():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Simulated push failure")
        return original_do_publish()

    with patch.object(tx, '_do_publish', side_effect=mock_do_publish):
        success = tx.finish_editing()
        assert not success
        assert tx.state == WriteTransactionState.OFFLINE_PENDING_PUBLISH

        # Check lock retained
        assert cm.is_writing()
        assert cm.get_lock_owner() is not None

        # Check pending version exists
        pending = version_manager.get_pending_version()
        assert pending is not None
        assert pending == 2

        # Retry publish
        retry_success = tx.retry_publish()
        assert retry_success

        # After successful publish, lock is released and state is IDLE
        assert not cm.is_writing()
        assert tx.state == WriteTransactionState.IDLE

        # Check version published
        published = version_manager.get_current_version()
        assert published == 2
        assert version_manager.get_pending_version() is None

        # Fetch remote to update refs
        provider.fetch()

        # Check remote manifest exists and has correct version
        remote_manifest = provider.remote_manifest()
        assert remote_manifest is not None
        assert remote_manifest.get("runtime_version") == 2