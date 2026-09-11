# -*- coding: utf-8 -*-
"""Tests for remote lock lease renewal."""

import pytest
import subprocess
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


@pytest.fixture
def seeded_remote(tmp_path):
    """Create a seeded bare remote repository."""
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, capture_output=True, check=True)

    source_path = tmp_path / "source"
    source_path.mkdir()
    subprocess.run(["git", "init"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=source_path, capture_output=True, check=True)

    (source_path / "README.md").write_text("# Test repo")
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
    with open(source_path / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    subprocess.run(["git", "branch", "-M", "main"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "add", "."], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial"], cwd=source_path, capture_output=True, check=True)
    subprocess.run(["git", "push", str(remote_path), "main"], cwd=source_path, capture_output=True, check=True)

    return remote_path


def get_main_head(repo_path: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def get_main_branch(repo_path: Path) -> str:
    return subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def get_main_status(repo_path: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True
    ).stdout.strip()


def remote_lock_exists(remote_path: Path) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", str(remote_path), "refs/heads/lock-main"],
        capture_output=True,
        text=True
    )
    return bool(result.stdout.strip())


class TestLockLeaseRenewal:
    """Test suite for remote lock lease renewal."""

    @pytest.fixture(autouse=True)
    def setup_repo(self, seeded_remote, tmp_path):
        self.repo_path = tmp_path / "repo"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(seeded_remote), str(self.repo_path)],
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.repo_path,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_path,
            check=True
        )
        self.remote_path = seeded_remote
        self.provider = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(seeded_remote),
            token="",
            branch="main"
        )
        self.provider.connect()
        yield
        if remote_lock_exists(self.remote_path):
            subprocess.run(
                ["git", "push", str(self.remote_path), "--delete", "lock-main", "--force"],
                capture_output=True
            )

    # ---- Test A: Basic Renewal ----
    def test_basic_renewal(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_001",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = self.provider.acquire_lock(lock_data)
        assert success is True

        # Verify lock exists
        status = self.provider.remote_lock_status()
        assert status["locked"] is True
        assert status["session_id"] == "sess_001"
        initial_expiry = status.get("lease_expires_at")
        # Either lease_expires_at or last_heartbeat should exist
        assert initial_expiry is not None or status.get("last_heartbeat") is not None

        # Wait a bit
        time.sleep(1)

        # Renew
        renewal_success = self.provider.renew_lock("user_a", "sess_001")
        assert renewal_success is True

        # Verify lease expiry moved forward if using lease_expires_at
        status_after = self.provider.remote_lock_status()
        new_expiry = status_after.get("lease_expires_at")
        if initial_expiry is not None and new_expiry is not None:
            assert datetime.fromisoformat(new_expiry) > datetime.fromisoformat(initial_expiry)

        # Each successful renewal advances the remote lease revision without
        # touching MAIN.
        assert status_after.get("lease_revision", 0) >= status.get("lease_revision", 0) + 1

        # Verify owner/session unchanged
        assert status_after.get("owner") == "user_a"
        assert status_after.get("session_id") == "sess_001"

        self.provider.release_lock("user_a")

    # ---- Test B: Wrong Owner ----
    def test_wrong_owner_renewal_fails(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_002",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data)

        # Renew with wrong owner
        result = self.provider.renew_lock("user_b", "sess_002")
        assert result is False

        # Verify lock unchanged
        status = self.provider.remote_lock_status()
        assert status.get("owner") == "user_a"
        assert status.get("session_id") == "sess_002"

        self.provider.release_lock("user_a")

    # ---- Test C: Wrong Session ----
    def test_wrong_session_renewal_fails(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_003",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data)

        # Renew with wrong session
        result = self.provider.renew_lock("user_a", "sess_wrong")
        assert result is False

        # Verify lock unchanged
        status = self.provider.remote_lock_status()
        assert status.get("session_id") == "sess_003"

        self.provider.release_lock("user_a")

    # ---- Test D: Renewal Race ----
    def test_renewal_race(self):
        # A acquires lock
        lock_data_a = {
            "locked": True,
            "session_id": "sess_A",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data_a)

        # Capture expected OID for A
        expected_oid = self.provider._remote_lock_oid()
        assert expected_oid is not None

        # B acquires lock (simulate race: B replaces A's lock)
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()

        # Make A's lock stale so B can acquire
        stale_lock = lock_data_a.copy()
        stale_lock["lease_expires_at"] = (datetime.now() - timedelta(seconds=10)).isoformat()
        stale_lock["last_heartbeat"] = (datetime.now() - timedelta(seconds=70)).isoformat()
        stale_commit = self.provider._create_lock_commit_plumbing(stale_lock, expected_oid)
        self.provider._push_lock_branch(stale_commit, expected_oid)

        # B acquires (should succeed because lock is stale)
        lock_data_b = {
            "locked": True,
            "session_id": "sess_B",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success_b = provider_b.acquire_lock(lock_data_b)
        assert success_b is True

        # A tries to renew (should fail because lock state changed)
        result = self.provider.renew_lock("user_a", "sess_A")
        assert result is False

        # Verify B's lock still exists
        status = self.provider.remote_lock_status()
        assert status.get("owner") == "user_b"
        assert status.get("session_id") == "sess_B"

        provider_b.release_lock("user_b")

    # ---- Test E: Expired Lock Cannot Renew ----
    def test_expired_lock_renewal_fails(self):
        # Create an expired lock using plumbing
        lock_data = {
            "locked": True,
            "session_id": "sess_expired",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": (datetime.now() - timedelta(seconds=70)).isoformat(),
            "last_heartbeat": (datetime.now() - timedelta(seconds=70)).isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
        }
        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # Try to renew (should fail because lock is expired)
        result = self.provider.renew_lock("user_a", "sess_expired")
        assert result is False

        # Verify lock still expired
        status = self.provider.remote_lock_status()
        assert status.get("locked") is True
        assert status.get("session_id") == "sess_expired"
        # The lock is expired, so renew should have failed.

        # Cleanup: force release
        self.provider.force_release("user_a")

    # ---- Test F: MAIN Isolation ----
    def test_renewal_main_isolation(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_iso",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data)

        before_head = get_main_head(self.repo_path)
        before_branch = get_main_branch(self.repo_path)
        before_status = get_main_status(self.repo_path)

        self.provider.renew_lock("user_a", "sess_iso")

        after_head = get_main_head(self.repo_path)
        after_branch = get_main_branch(self.repo_path)
        after_status = get_main_status(self.repo_path)

        assert after_head == before_head
        assert after_branch == before_branch
        assert after_status == before_status

        self.provider.release_lock("user_a")

    # ---- Test G: No MAIN Commit ----
    def test_renewal_no_main_commit(self):
        lock_data = {
            "locked": True,
            "session_id": "sess_nocommit",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data)

        # Count commits before renewal
        before_commits = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()

        self.provider.renew_lock("user_a", "sess_nocommit")

        after_commits = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()

        assert after_commits == before_commits, "MAIN commit count changed"

        self.provider.release_lock("user_a")

    # ---- Test H: FINISHING Deadline Preservation ----
    def test_renewal_does_not_extend_finishing_deadline(self):
        # Create a lock with finishing data using plumbing
        now = datetime.now()
        deadline = now + timedelta(seconds=120)
        lock_data = {
            "locked": True,
            "session_id": "sess_finish",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "finishing_started_at": now.isoformat(),
            "finishing_deadline": deadline.isoformat(),
            "publish_intent": True,
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
        }
        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # Read deadline before renewal
        status_before = self.provider.remote_lock_status()
        deadline_before = status_before.get("finishing_deadline")
        assert deadline_before is not None

        # Renew
        self.provider.renew_lock("user_a", "sess_finish")

        # Read deadline after renewal
        status_after = self.provider.remote_lock_status()
        deadline_after = status_after.get("finishing_deadline")

        assert deadline_after == deadline_before, "FINISHING deadline changed"

        # Cleanup
        self.provider.release_lock("user_a")

    # ---- Test I: Expired Lock Can Be Acquired ----
    def test_expired_lock_can_be_acquired(self):
        # Create an expired lock
        lock_data = {
            "locked": True,
            "session_id": "sess_expired2",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": (datetime.now() - timedelta(seconds=70)).isoformat(),
            "last_heartbeat": (datetime.now() - timedelta(seconds=70)).isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
        }
        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # Another user should be able to acquire because lock is expired
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()

        lock_data_b = {
            "locked": True,
            "session_id": "sess_B2",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat(),
            "machine": "test_machine",
        }
        success = provider_b.acquire_lock(lock_data_b)
        assert success is True, "Should be able to acquire expired lock"

        status = provider_b.remote_lock_status()
        assert status.get("owner") == "user_b"
        assert status.get("session_id") == "sess_B2"

        provider_b.release_lock("user_b")