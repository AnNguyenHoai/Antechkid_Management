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
)
from centermanager.events.event_bus import EventBus


class TestSyncResult:
    def test_values(self):
        assert SyncResult.SUCCESS.value == "success"
        assert SyncResult.FAILED.value == "failed"
        assert SyncResult.CANCELLED.value == "cancelled"
        assert SyncResult.NO_CHANGE.value == "no_change"
        assert SyncResult.OFFLINE.value == "offline"
        assert SyncResult.CONFLICT.value == "conflict"


class TestSynchronizationResult:
    def test_creation(self):
        result = SynchronizationResult(
            result=SyncResult.SUCCESS,
            message="OK",
            provider="test",
            current_version=5,
            remote_version=5,
        )
        assert result.is_success() is True
        assert result.is_failed() is False
        assert result.has_change() is True

    def test_failed_result(self):
        result = SynchronizationResult(result=SyncResult.FAILED, message="Error")
        assert result.is_success() is False
        assert result.is_failed() is True


class TestVersionResolver:
    def test_up_to_date(self):
        resolver = VersionResolver()
        status = resolver.resolve(10, 10)
        assert status == VersionStatus.UP_TO_DATE

    def test_outdated(self):
        resolver = VersionResolver()
        status = resolver.resolve(5, 10)
        assert status == VersionStatus.OUTDATED

    def test_unknown_remote(self):
        resolver = VersionResolver()
        status = resolver.resolve(5, None)
        assert status == VersionStatus.UNKNOWN

    def test_conflict(self):
        resolver = VersionResolver()
        status = resolver.resolve(10, 5)
        assert status == VersionStatus.CONFLICT

    def test_needs_sync(self):
        resolver = VersionResolver()
        assert resolver.needs_sync(5, 10) is True
        assert resolver.needs_sync(5, None) is True
        assert resolver.needs_sync(5, 5) is False

    def test_is_conflict(self):
        resolver = VersionResolver()
        assert resolver.is_conflict(10, 5) is True
        assert resolver.is_conflict(5, 10) is False


class TestSynchronizationPolicy:
    def test_on_startup_if_outdated(self):
        policy = SynchronizationPolicy(SyncPolicy.ON_STARTUP_IF_OUTDATED)
        assert policy.should_sync_on_startup(True) is True
        assert policy.should_sync_on_startup(False) is False
        assert policy.should_sync_background() is False

    def test_always(self):
        policy = SynchronizationPolicy(SyncPolicy.ALWAYS)
        assert policy.should_sync_on_startup(True) is True
        assert policy.should_sync_on_startup(False) is True

    def test_background(self):
        policy = SynchronizationPolicy(SyncPolicy.BACKGROUND)
        assert policy.should_sync_on_startup(True) is True
        assert policy.should_sync_background() is True

    def test_manual(self):
        policy = SynchronizationPolicy(SyncPolicy.MANUAL)
        assert policy.should_sync_on_startup(True) is False
        assert policy.should_sync_manual() is False

    def test_from_config(self):
        config = {"sync_policy": "background"}
        policy = SynchronizationPolicy.from_config(config)
        assert policy.policy == SyncPolicy.BACKGROUND

        # Invalid config fallback
        config = {"sync_policy": "invalid"}
        policy = SynchronizationPolicy.from_config(config)
        assert policy.policy == SyncPolicy.ON_STARTUP_IF_OUTDATED


class TestRetryPolicy:
    def test_execute_success(self):
        calls = [0]
        def operation():
            calls[0] += 1
            return True
        policy = RetryPolicy(max_retries=3)
        result = policy.execute(operation, "test")
        assert result is True
        assert calls[0] == 1

    def test_execute_retry_success(self):
        calls = [0]
        def operation():
            calls[0] += 1
            if calls[0] < 3:
                return False
            return True
        policy = RetryPolicy(max_retries=3, retry_interval=0.01)
        result = policy.execute(operation, "test")
        assert result is True
        assert calls[0] == 3

    def test_execute_fail(self):
        calls = [0]
        def operation():
            calls[0] += 1
            return False
        policy = RetryPolicy(max_retries=2, retry_interval=0.01)
        result = policy.execute(operation, "test")
        assert result is False
        assert calls[0] == 3

    def test_execute_exception(self):
        calls = [0]
        def operation():
            calls[0] += 1
            raise ValueError("Test error")
        policy = RetryPolicy(max_retries=2, retry_interval=0.01)
        result = policy.execute(operation, "test")
        assert result is False
        assert calls[0] == 3


class TestGitSynchronizationProvider:
    def test_creation(self, tmp_path):
        """Test creation without repo."""
        provider = GitSynchronizationProvider(tmp_path)
        assert provider.name() == "git"
        assert provider.health() is False
        assert provider.is_configured() is False

    def test_connect(self, tmp_path):
        """Test connect with existing repo."""
        # Create a real Git repo
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
        # No remote, should return None
        manifest = provider.remote_manifest()
        assert manifest is None

    def test_fetch_publish_not_implemented(self, tmp_path):
        from centermanager.platform.synchronization.exceptions import RemoteUnavailableError
        """Test fetch and publish with local repo (no remote)."""
        import git
        repo = git.Repo.init(tmp_path)
        (tmp_path / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")

        provider = GitSynchronizationProvider(tmp_path)
        provider.connect()
        # Fetch works without remote
        assert provider.fetch() is True
        # Publish with no remote – should raise RemoteUnavailableError
        with pytest.raises(RemoteUnavailableError):
            provider.publish("test", "user")

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
        # Non-existent path
        non_existent = tmp_path / "non_existent"
        provider = GitSynchronizationProvider(non_existent)
        assert provider.validate() is False
        
        # Valid repo
        import git
        repo = git.Repo.init(non_existent)
        (non_existent / "test.txt").write_text("test")
        repo.index.add(["test.txt"])
        repo.index.commit("Initial commit")
        
        assert provider.validate() is True