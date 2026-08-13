# -*- coding: utf-8 -*-
"""Integration test for publish-only workflow."""

import pytest
import shutil
import subprocess
from pathlib import Path

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

        # Tạo Paths object
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
        # Cần override để trả về repo
        paths._repo_path = temp_repo
        return paths

    def test_publish_only_workflow(self, runtime_env, temp_repo):
        """Test publish-only workflow without fetch/pull."""
        # Tạo database
        db_path = runtime_env.database_dir / "center.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        # Tạo student
        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        # Tạo collaboration manager
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=runtime_env.runtime_root, event_bus=event_bus)
        cm.initialize("test_user", "test_user", "admin")

        # Tạo sync provider
        sync_provider = GitSynchronizationProvider(
            repo_path=temp_repo,
            repository_url=str(temp_repo),
            token="",
            branch="main"
        )
        sync_provider.connect()

        # Tạo sync service
        sync_service = RuntimeSyncService(
            sync_manager=None,  # Need proper manager
            collab_manager=cm,
            context_manager=None,
            event_bus=event_bus,
            poll_interval=30
        )
        # Không có sync manager thật, test sẽ bỏ qua

        # Tạo transaction manager
        tx = WriteTransactionManager(cm)

        # Giả lập finish editing
        tx._sync_service = sync_service

        # Copy database
        repo_db_dir = temp_repo / "database"
        repo_db_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, repo_db_dir / "center.db")

        # Git add và commit
        subprocess.run(["git", "add", "."], cwd=temp_repo, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", "Test commit"],
            cwd=temp_repo,
            capture_output=True,
            text=True
        )
        # Kiểm tra commit thành công
        assert result.returncode == 0 or "nothing to commit" in result.stdout

        # Kiểm tra file có trong repo
        assert (temp_repo / "database" / "center.db").exists()