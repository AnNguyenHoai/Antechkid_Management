# -*- coding: utf-8 -*-
"""Integration test for publish-only workflow."""

import pytest
import shutil
import subprocess
import json
from pathlib import Path
from unittest.mock import patch

from centermanager.core.paths import Paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.write_transaction import WriteTransactionManager
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.events.event_bus import EventBus
from sqlalchemy.orm import sessionmaker


class TestPublishOnly:
    @pytest.fixture
    def temp_repo(self, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)
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

        class TestPaths(Paths):
            def __init__(self, r, repo):
                self._runtime_root = r
                self._project_root = r.parent
                super().__init__()
                self._runtime_root = r
            @property
            def runtime_root(self):
                return self._runtime_root

        paths = TestPaths(root, temp_repo)
        paths._repo_path = temp_repo
        return paths

    def test_publish_only_workflow(self, runtime_env, temp_repo):
        """Test publish-only workflow without fetch/pull (legacy integration test)."""
        db_path = runtime_env.database_dir / "center.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=runtime_env.runtime_root, event_bus=event_bus)
        cm.initialize("test_user", "test_user", "admin")

        sync_provider = GitSynchronizationProvider(
            repo_path=temp_repo,
            repository_url=str(temp_repo),
            token="",
            branch="main"
        )
        sync_provider.connect()

        sync_service = RuntimeSyncService(
            sync_manager=None,
            collab_manager=cm,
            context_manager=None,
            event_bus=event_bus,
            poll_interval=30
        )
        tx = WriteTransactionManager(cm)
        tx._sync_service = sync_service

        repo_db_dir = temp_repo / "database"
        repo_db_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, repo_db_dir / "center.db")

        subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", "Test commit"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )
        assert result.returncode == 0 or "nothing to commit" in result.stdout
        assert (temp_repo / "database" / "center.db").exists()

    def test_git_provider_publish_only_no_remote_sync(self, fresh_center_manager_remote, tmp_path):
        """
        Test that GitSynchronizationProvider.publish_only() does NOT perform
        any remote synchronization (fetch/pull/rebase/merge/reset).
        Only commit + push are allowed.
        """
        repo_path = tmp_path / "repo"
        # FIX: add --branch main to ensure checkout
        subprocess.run(
            ["git", "clone", "--branch", "main", str(fresh_center_manager_remote), str(repo_path)],
            check=True
        )

        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(fresh_center_manager_remote),
            token="",
            branch="main"
        )
        provider.connect()

        # Create a local change (update manifest)
        manifest_path = repo_path / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["runtime_version"] = 2
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Capture git commands
        commands = []
        original_run = provider._run_git_command

        def capture_run(args, cwd=None):
            commands.append(args)
            return original_run(args, cwd=cwd)

        with patch.object(provider, '_run_git_command', side_effect=capture_run):
            result = provider.publish_only("Test publish-only", "test_user")

        assert result is True

        # Analyze captured commands
        command_strings = [" ".join(cmd) for cmd in commands]

        # Assert NO remote synchronization
        assert not any("fetch" in cmd for cmd in command_strings)
        assert not any("pull" in cmd for cmd in command_strings)
        assert not any("rebase" in cmd for cmd in command_strings)
        assert not any("merge" in cmd for cmd in command_strings)
        assert not any("reset" in cmd for cmd in command_strings)

        # Assert commit and push are present
        assert any("commit" in cmd for cmd in command_strings), "No commit found"
        assert any("push" in cmd for cmd in command_strings), "No push found"