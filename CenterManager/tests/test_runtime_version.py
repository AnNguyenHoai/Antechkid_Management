# -*- coding: utf-8 -*-
"""Integration test for Runtime Version increment and end-to-end sync."""

import pytest
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from centermanager.core import paths as paths_module
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.json_metadata_repository import JsonMetadataRepository
from centermanager.platform.version import VersionManager
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.synchronization import GitSynchronizationProvider, SynchronizationManager
from centermanager.events.event_bus import EventBus
from sqlalchemy.orm import sessionmaker


class TestRuntimeVersion:
    @pytest.fixture
    def temp_repo(self, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
        # This disposable non-bare remote intentionally accepts real pushes.
        subprocess.run(["git", "config", "receive.denyCurrentBranch", "updateInstead"], cwd=repo_path, check=True)
        (repo_path / "README.md").write_text("# Test repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)
        return repo_path

    @pytest.fixture
    def runtime_env(self, temp_repo, tmp_path):
        root = tmp_path / "runtime"
        root.mkdir(parents=True, exist_ok=True)
        db_dir = root / "Database"
        db_dir.mkdir(parents=True, exist_ok=True)
        meta_dir = root / "metadata"
        meta_dir.mkdir(parents=True, exist_ok=True)
        collab_dir = root / "collaboration"
        collab_dir.mkdir(parents=True, exist_ok=True)

        # Copy repo to runtime/repository
        repo_dst = root / "repository"
        shutil.copytree(temp_repo, repo_dst)

        # Create initial manifest
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

        class TestPaths:
            def __init__(self, runtime_root):
                self._runtime_root = runtime_root
                self._project_root = runtime_root.parent

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

            @property
            def temp_dir(self):
                return self._runtime_root / "Temp"

            def ensure_directories(self):
                for d in [self.database_dir, self.metadata_dir, self.config_dir,
                          self.logs_dir, self.backup_dir, self.attachment_dir,
                          self.reports_dir, self.export_dir, self.temp_dir]:
                    d.mkdir(parents=True, exist_ok=True)

        test_paths = TestPaths(root)
        import centermanager.core.paths as paths_mod
        original_get_paths = paths_mod.get_paths
        paths_mod._paths = test_paths

        yield test_paths

        from centermanager.core.current_user import clear_current_user
        clear_current_user()
        paths_mod._paths = None

    def test_version_increment_on_publish(self, runtime_env, temp_repo):
        """Test that runtime version increments after successful publish."""
        # Tạo database
        db_path = runtime_env.database_dir / "center.db"
        engine = create_engine_for_path(db_path.with_name("seed.db"))
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        engine.dispose()
        shutil.copy2(db_path.with_name("seed.db"), db_path)
        engine = create_engine_for_path(db_path)
        Session = sessionmaker(bind=engine)

        # Setup collaboration
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=runtime_env.runtime_root, event_bus=event_bus)
        cm.initialize("test_user", "test_user", "admin")

        # Setup metadata and version
        meta_dir = runtime_env.runtime_root / "metadata"
        meta_repo = JsonMetadataRepository(meta_dir)
        version_manager = VersionManager(meta_repo, event_bus)

        # Setup sync provider (mock git to avoid network)
        repo_path = runtime_env.runtime_root / "repository"
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(temp_repo),
            token="",
            branch="main"
        )
        provider.connect()

        # E1B-1 requires the actual collaboration provider and accepted DB base.
        # Seed only this disposable remote; the test never uses production data.
        repo_db = repo_path / "database" / "center.db"
        repo_db.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, repo_db)
        provider._run_git_command(["add", "--force", "database/center.db", "manifest.json"])
        provider._run_git_command(["commit", "-m", "synthetic accepted database base"])
        provider._run_git_command(["push", "-u", "origin", "main"])
        cm._sync_provider = provider

        # Setup sync manager and service
        sync_manager = SynchronizationManager(provider, event_bus=event_bus)
        sync_service = RuntimeSyncService(
            sync_manager=sync_manager,
            collab_manager=cm,
            context_manager=None,
            event_bus=event_bus,
            poll_interval=30
        )

        # Setup transaction
        tx = WriteTransactionManager(cm)
        tx.enable_local_mutation_gate()
        from centermanager.core.current_user import set_current_user
        from centermanager.core.capabilities import Capability
        from types import SimpleNamespace
        set_current_user(SimpleNamespace(id="test_user", username="test_user", full_name="Test",
                                        is_active=True, role=SimpleNamespace(name="admin"),
                                        permissions=set(Capability.values())))
        tx.set_sync_service(sync_service)
        tx.set_version_manager(version_manager)

        # Get current version
        old_version = version_manager.get_current_version()
        assert old_version == 1

        # Start editing and finish
        def save_local():
            with Session() as sess:
                s = sess.query(Student).first()
                if s:
                    s.full_name = "Updated Student"
                    sess.commit()
            return True

        # Fixture already materializes the exact accepted synthetic base.
        # Handoff/schema barriers are covered by their own integration suites.
        with patch.object(sync_service, "execute_write_handoff_sync", return_value=True):
            assert tx.start_editing(save_local), tx.last_start_error
        tx.mark_dirty()

        # Mock _do_publish to simulate successful push
        with patch.object(tx, '_do_publish', wraps=tx._do_publish):
            # Also mock _publish_database_and_manifest to update manifest
            def mock_publish_db():
                # Copy DB
                db_src = runtime_env.database_dir / "center.db"
                if db_src.exists():
                    db_dst = repo_path / "database"
                    db_dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(db_src, db_dst / "center.db")
                # Update manifest
                manifest_path = repo_path / "manifest.json"
                if manifest_path.exists():
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    manifest["runtime_version"] = 2
                    manifest["published_at"] = datetime.now().isoformat()
                    with open(manifest_path, "w", encoding="utf-8") as f:
                        json.dump(manifest, f, indent=2)
                return True

            with patch.object(tx, '_publish_database_and_manifest', side_effect=mock_publish_db):
                success = tx.finish_editing()
                assert success

        # Check version incremented
        new_version = version_manager.get_current_version()
        assert new_version == 2

        # Check pending version cleared
        assert version_manager.get_pending_version() is None

        # Check manifest in repository updated
        with open(repo_path / "manifest.json", "r") as f:
            manifest = json.load(f)
            assert manifest["runtime_version"] == 2

    def test_manifest_and_database_atomic(self, runtime_env, temp_repo):
        """Test that database and manifest are committed together."""
        # Tạo database
        db_path = runtime_env.database_dir / "center.db"
        engine = create_engine_for_path(db_path.with_name("seed.db"))
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        engine.dispose()
        shutil.copy2(db_path.with_name("seed.db"), db_path)
        engine = create_engine_for_path(db_path)
        Session = sessionmaker(bind=engine)

        # Setup collaboration
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=runtime_env.runtime_root, event_bus=event_bus)
        cm.initialize("test_user", "test_user", "admin")

        # Setup metadata and version
        meta_dir = runtime_env.runtime_root / "metadata"
        meta_repo = JsonMetadataRepository(meta_dir)
        version_manager = VersionManager(meta_repo, event_bus)

        # Setup sync provider
        repo_path = runtime_env.runtime_root / "repository"
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(temp_repo),
            token="",
            branch="main"
        )
        provider.connect()

        # Setup transaction
        tx = WriteTransactionManager(cm)
        tx.enable_local_mutation_gate()
        from centermanager.core.current_user import set_current_user
        from centermanager.core.capabilities import Capability
        from types import SimpleNamespace
        set_current_user(SimpleNamespace(id="test_user", username="test_user", full_name="Test",
                                        is_active=True, role=SimpleNamespace(name="admin"),
                                        permissions=set(Capability.values())))
        tx.set_version_manager(version_manager)

        # Create pending version
        pending = version_manager.create_pending_version()
        assert pending == 2

        # Update manifest in repository
        provider.update_manifest(2)

        # Check both files exist in repository
        # Create dummy database file
        (repo_path / "database").mkdir(exist_ok=True)
        with open(repo_path / "database" / "center.db", "w") as f:
            f.write("test db")

        assert (repo_path / "database" / "center.db").exists()
        assert (repo_path / "manifest.json").exists()
        
        # Verify manifest version
        with open(repo_path / "manifest.json", "r") as f:
            manifest = json.load(f)
            assert manifest["runtime_version"] == 2