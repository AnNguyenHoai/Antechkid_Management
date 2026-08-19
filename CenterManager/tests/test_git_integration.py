# -*- coding: utf-8 -*-
"""Integration tests for GitSynchronizationProvider."""

import pytest
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

import git
from centermanager.platform.synchronization import (
    GitSynchronizationProvider,
    SynchronizationManager,
    RepositoryConflictError,
    AuthenticationFailedError,
    CloneFailedError,
)


def create_bare_remote(source_repo, remote_path):
    """Create a bare remote repository from source repo."""
    remote_path.mkdir(parents=True, exist_ok=True)
    remote_repo = git.Repo.init(remote_path, bare=True)
    
    # Ensure source repo has at least one commit
    if not source_repo.head.is_valid():
        # Create initial commit
        (source_repo.working_dir / "initial.txt").write_text("initial")
        source_repo.index.add(["initial.txt"])
        source_repo.index.commit("Initial commit")
    
    # Get branch name (main or master)
    branch_name = source_repo.active_branch.name
    
    # Add remote and push
    origin = source_repo.create_remote("origin", str(remote_path))
    origin.push(refspec=f"{branch_name}:{branch_name}")
    
    return remote_repo, branch_name


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary Git repository with remote."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir(parents=True, exist_ok=True)
    
    repo = git.Repo.init(repo_path)
    
    # Create initial manifest
    manifest_path = repo_path / "manifest.json"
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
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    
    repo.index.add(["manifest.json"])
    repo.index.commit("Initial commit")
    
    remote_path = tmp_path / "remote.git"
    remote_repo, branch_name = create_bare_remote(repo, remote_path)
    
    return repo_path, remote_path, repo, branch_name


class TestGitIntegration:
    def test_clone(self, tmp_path):
        """Test cloning a repository."""
        # Create source repo
        source_path = tmp_path / "source"
        source_path.mkdir(parents=True, exist_ok=True)
        
        source_repo = git.Repo.init(source_path)
        
        # Create manifest and commit
        manifest_path = source_path / "manifest.json"
        manifest = {
            "schema_version": 1,
            "runtime_version": 5,
            "database_version": 1,
            "minimum_app_version": "0.1.0",
            "publisher": "Test",
            "branch": "main",
            "created_at": datetime.now().isoformat(),
            "published_at": None,
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        
        source_repo.index.add(["manifest.json"])
        source_repo.index.commit("Initial commit")
        
        # Create bare remote
        remote_path = tmp_path / "remote.git"
        remote_repo, branch_name = create_bare_remote(source_repo, remote_path)
        
        # Clone using provider
        clone_path = tmp_path / "clone"
        provider = GitSynchronizationProvider(
            repo_path=clone_path,
            repository_url=str(remote_path),
            token="test",
            branch=branch_name,
        )
        
        provider.connect()
        result = provider.clone()
        
        assert result is True
        assert clone_path.exists()
        assert (clone_path / ".git").exists()
        assert (clone_path / "manifest.json").exists()
        
        # Verify manifest
        with open(clone_path / "manifest.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["runtime_version"] == 5
    
    def test_fetch_and_pull(self, temp_git_repo):
        """Test fetch and pull operations."""
        repo_path, remote_path, repo, branch_name = temp_git_repo
        
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(remote_path),
            token="test",
            branch=branch_name,
        )
        
        provider.connect()
        
        # Fetch
        assert provider.fetch() is True
        
        # Check current version
        assert provider.current_version() == 1
        
        # Make remote change using a clone
        temp_clone_dir = tempfile.mkdtemp()
        clone = git.Repo.clone_from(str(remote_path), temp_clone_dir)
        
        manifest_path = Path(temp_clone_dir) / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["runtime_version"] = 2
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        clone.index.add(["manifest.json"])
        clone.index.commit("Update version to 2")
        clone.remotes.origin.push(refspec=f"{branch_name}:{branch_name}")
        
        shutil.rmtree(temp_clone_dir, ignore_errors=True)
        
        # Pull changes
        assert provider.pull() is True
        
        # Verify version updated
        assert provider.current_version() == 2
    
    def test_publish(self, temp_git_repo):
        repo_path, remote_path, repo, branch_name = temp_git_repo
        
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(remote_path),
            token="test",
            branch=branch_name,
        )
        
        provider.connect()
        
        # Tạo database trước khi publish
        db_dir = repo_path / "database"
        db_dir.mkdir(parents=True, exist_ok=True)
        (db_dir / "center.db").touch()
        
        # Update manifest locally
        manifest_path = repo_path / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["runtime_version"] = 3
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        assert provider.publish("Update to version 3", "test_user") is True
    
    def test_health(self, temp_git_repo):
        """Test health check."""
        repo_path, remote_path, repo, branch_name = temp_git_repo
        
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(remote_path),
            token="test",
            branch=branch_name,
        )
        
        # Before connect
        assert provider.health() is False
        
        provider.connect()
        assert provider.health() is True
    
    def test_remote_manifest(self, temp_git_repo):
        """Test remote manifest retrieval."""
        repo_path, remote_path, repo, branch_name = temp_git_repo
        
        provider = GitSynchronizationProvider(
            repo_path=repo_path,
            repository_url=str(remote_path),
            token="test",
            branch=branch_name,
        )
        
        provider.connect()
        
        # Make remote change
        temp_clone_dir = tempfile.mkdtemp()
        clone = git.Repo.clone_from(str(remote_path), temp_clone_dir)
        
        manifest_path = Path(temp_clone_dir) / "manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["runtime_version"] = 10
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        clone.index.add(["manifest.json"])
        clone.index.commit("Update to version 10")
        clone.remotes.origin.push(refspec=f"{branch_name}:{branch_name}")
        
        shutil.rmtree(temp_clone_dir, ignore_errors=True)
        
        # Get remote manifest
        manifest = provider.remote_manifest()
        assert manifest is not None
        assert manifest["runtime_version"] == 10