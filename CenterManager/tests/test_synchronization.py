# -*- coding: utf-8 -*-
"""Tests for Synchronization Infrastructure."""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock

from centermanager.platform.synchronization import (
    SynchronizationManager,
    SynchronizationProvider,
    GitSynchronizationProvider,
    SynchronizationPolicy,
    SyncPolicy,
    VersionResolver,
    VersionStatus,
    SynchronizationResult,
    SyncResult,
    RetryPolicy,
    SynchronizationStarted,
    SynchronizationFinished,
    SynchronizationFailed,
    VersionChecked,
    RemoteUnavailableError,
    PushFailedError,
)
from centermanager.events.event_bus import EventBus


# ... (các test khác giữ nguyên) ...

class TestGitSynchronizationProvider:
    def test_creation(self, tmp_path):
        """Test creation without repo."""
        provider = GitSynchronizationProvider(tmp_path)
        assert provider.name() == "git"
        assert provider.health() is False
        assert provider.is_configured() is False

    def test_connect(self, tmp_path):
        """Test connect with existing repo."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(tmp_path)
        assert provider.connect() is True
        assert provider.health() is True

    def test_status(self, tmp_path):
        """Test status."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        status = provider.status()
        assert status["provider"] == "git"
        assert status["connected"] is True

    def test_remote_manifest(self, tmp_path):
        """Test remote manifest without remote."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        manifest = provider.remote_manifest()
        assert manifest is None

    def test_fetch_publish_not_implemented(self, tmp_path):
        """Test fetch and publish with local repo (no remote)."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        
        # No remote origin, fetch should return True (no-op)
        assert provider.fetch() is True
        
        # No remote origin, publish should return True (no-op)
        assert provider.publish("test", "user") is True

    def test_pull(self, tmp_path):
        """Test pull with local repo."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        # Pull without remote returns True (already up to date)
        assert provider.pull() is True

    def test_is_offline(self, tmp_path):
        """Test offline detection."""
        provider = GitSynchronizationProvider(tmp_path)
        assert provider.is_offline() is True
        provider.connect()
        assert provider.is_offline() is False
        provider.disconnect()
        assert provider.is_offline() is True

    def test_validate(self, tmp_path):
        """Test validate."""
        non_existent = tmp_path / "non_existent"
        provider = GitSynchronizationProvider(non_existent)
        assert provider.validate() is False
        
        import git
        repo = git.Repo.init(non_existent)
        (non_existent / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(non_existent)
        assert provider.validate() is True

    def test_publish_without_changes(self, tmp_path):
        """Test publish without changes."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        # No changes, publish should return True
        assert provider.publish("no changes", "user") is True