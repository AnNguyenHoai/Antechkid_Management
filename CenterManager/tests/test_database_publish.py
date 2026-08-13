# -*- coding: utf-8 -*-
"""Integration test for database publish to Git."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from centermanager.core.paths import Paths
from centermanager.database.engine import create_engine_for_path
from centermanager.database.base import Base
from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.platform.synchronization.git.git_provider import GitProvider
from centermanager.platform.synchronization.git.git_credentials import GitCredentials
from sqlalchemy.orm import sessionmaker


class TestDatabasePublish:
    """Test database sync via Git."""

    @pytest.fixture
    def temp_repo(self, tmp_path):
        """Create temporary Git repository."""
        repo_path = tmp_path / "repo"
        repo_path.mkdir(parents=True, exist_ok=True)

        # Init repo
        subprocess.run(["git", "init"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, capture_output=True)

        # Create initial commit
        (repo_path / "README.md").write_text("# Test repo")
        subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, capture_output=True)

        return repo_path

    @pytest.fixture
    def runtime_paths(self, temp_repo):
        """Create runtime structure with repository."""
        class TestPaths(Paths):
            def __init__(self, root, repo):
                self._runtime_root = root
                self._project_root = root.parent
                self._repo_root = repo
                super().__init__()
                # Override runtime_root to point to temp
                self._runtime_root = root

            @property
            def runtime_root(self):
                return self._runtime_root

            @property
            def repository_root(self):
                return self._repo_root

        root = temp_repo.parent / "runtime"
        root.mkdir(parents=True, exist_ok=True)

        # Tạo database directory
        db_dir = root / "Database"
        db_dir.mkdir(parents=True, exist_ok=True)

        return TestPaths(root, temp_repo)

    def test_database_copy_to_repository(self, runtime_paths):
        """Test that database is copied to repository."""
        # Tạo database
        db_path = runtime_paths.database_dir / "center.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        # Tạo student
        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        # Copy database vào repository
        repo_db_dir = runtime_paths.repository_root / "database"
        repo_db_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, repo_db_dir / "center.db")

        # Verify
        assert (repo_db_dir / "center.db").exists()
        assert (repo_db_dir / "center.db").stat().st_size > 0

        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=runtime_paths.repository_root,
            capture_output=True,
            text=True
        )
        # Kiểm tra cả hai trường hợp: file mới (??) hoặc đã staged (A)
        assert ("database/center.db" in result.stdout or 
                "database/" in result.stdout), f"Database not detected: {result.stdout}"

    def test_git_commit_contains_database(self, runtime_paths):
        """Test that database is committed to Git."""
        # Tạo database
        db_path = runtime_paths.database_dir / "center.db"
        engine = create_engine_for_path(db_path)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            student = Student(student_code="HS001", full_name="Test Student")
            session.add(student)
            session.commit()

        # Copy database vào repository
        repo_db_dir = runtime_paths.repository_root / "database"
        repo_db_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, repo_db_dir / "center.db")

        # Thêm placeholder
        (runtime_paths.repository_root / "placeholder.txt").write_text("Test placeholder")

        # Git add và commit
        subprocess.run(["git", "add", "."], cwd=runtime_paths.repository_root, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add database and placeholder"],
            cwd=runtime_paths.repository_root,
            capture_output=True
        )

        # Verify commit contains database
        result = subprocess.run(
            ["git", "show", "--name-only", "HEAD"],
            cwd=runtime_paths.repository_root,
            capture_output=True,
            text=True
        )
        assert "database/center.db" in result.stdout or "database/center.db" in result.stderr