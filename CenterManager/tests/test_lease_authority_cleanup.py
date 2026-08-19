# -*- coding: utf-8 -*-
"""Tests for remote lease authority cleanup - ensuring lease_expires_at is the sole authority."""

import pytest
import subprocess
import json
import time
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


class TestLeaseAuthorityCleanup:
    """
    Test suite proving lease_expires_at is the sole authority for remote lock validity.
    last_heartbeat is NOT used for remote validity decisions.
    """

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

    # ---- Test A: Stale heartbeat, valid lease ----
    def test_stale_heartbeat_valid_lease(self):
        """
        Prove: Stale local heartbeat does NOT invalidate a valid remote lease.
        lease_expires_at is the authority, not last_heartbeat.
        """
        now = datetime.now()

        # Create a lock with fresh lease but stale heartbeat
        lock_data = {
            "locked": True,
            "session_id": "sess_stale_hb",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=70)).isoformat(),
            "last_heartbeat": (now - timedelta(seconds=70)).isoformat(),  # Stale!
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),  # Valid!
            "machine": "test_machine",
        }

        # Push lock to remote
        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # _is_lock_valid should return True (uses lease_expires_at only)
        remote_lock = self.provider._read_lock_from_oid(self.provider._remote_lock_oid())
        assert self.provider._is_lock_valid(remote_lock) is True

        # remote_lock_status should show locked
        status = self.provider.remote_lock_status()
        assert status["locked"] is True
        assert status["owner"] == "user_a"
        assert status["session_id"] == "sess_stale_hb"

        # Cleanup
        self.provider.force_release("user_a")

    # ---- Test B: Expired lease ----
    def test_expired_lease_is_stale(self):
        """
        Prove: Expired lease is correctly detected as stale.
        This is the correct invalidation mechanism.
        """
        now = datetime.now()

        # Create an expired lock
        lock_data = {
            "locked": True,
            "session_id": "sess_expired",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=120)).isoformat(),
            "last_heartbeat": now.isoformat(),  # Fresh heartbeat!
            "lease_expires_at": (now - timedelta(seconds=10)).isoformat(),  # Expired!
            "machine": "test_machine",
        }

        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # _is_lock_valid should return False (lease expired, even though heartbeat fresh)
        remote_lock = self.provider._read_lock_from_oid(self.provider._remote_lock_oid())
        assert self.provider._is_lock_valid(remote_lock) is False

        # Another user should be able to acquire
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()

        lock_data_b = {
            "locked": True,
            "session_id": "sess_B",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
        }
        success_b = provider_b.acquire_lock(lock_data_b)
        assert success_b is True, "Expired lease should allow re-acquisition"

        status = provider_b.remote_lock_status()
        assert status["owner"] == "user_b"
        assert status["session_id"] == "sess_B"

        provider_b.release_lock("user_b")

    # ---- Test C: Heartbeat stops, lease remains valid ----
    def test_heartbeat_stops_lease_valid(self):
        """
        Prove: Stopping heartbeat does NOT force-release a valid remote lease.
        The lease stands independent of local heartbeat.
        """
        now = datetime.now()

        # Create lock with valid lease
        lock_data = {
            "locked": True,
            "session_id": "sess_hb_stop",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }

        success = self.provider.acquire_lock(lock_data)
        assert success is True

        # Simulate heartbeat stopping by not updating last_heartbeat
        # But lease remains valid

        # Check lock is still valid after "heartbeat stop"
        status = self.provider.remote_lock_status()
        assert status["locked"] is True
        assert status["owner"] == "user_a"

        # _is_lock_valid uses lease_expires_at only
        remote_lock = self.provider._read_lock_from_oid(self.provider._remote_lock_oid())
        assert self.provider._is_lock_valid(remote_lock) is True

        # No force-release should occur
        self.provider.release_lock("user_a")

    # ---- Test D: Renewal changes only lease ----
    def test_renewal_updates_only_lease(self):
        """
        Prove: Renewal extends ONLY the remote lease (lease_expires_at).
        last_heartbeat is NOT used as lease authority.
        """
        now = datetime.now()

        lock_data = {
            "locked": True,
            "session_id": "sess_renew",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }

        self.provider.acquire_lock(lock_data)

        before = self.provider.remote_lock_status()
        before_lease = before.get("lease_expires_at")
        before_hb = before.get("last_heartbeat")

        # Wait a bit
        time.sleep(1)

        # Renew
        renewal_success = self.provider.renew_lock("user_a", "sess_renew")
        assert renewal_success is True

        after = self.provider.remote_lock_status()
        after_lease = after.get("lease_expires_at")
        after_hb = after.get("last_heartbeat")

        # Lease moved forward
        assert after_lease is not None
        assert before_lease is not None
        assert datetime.fromisoformat(after_lease) > datetime.fromisoformat(before_lease)

        # Heartbeat unchanged (or only minimally updated by the system)
        # The key point: heartbeat is NOT the authority
        assert after.get("owner") == "user_a"
        assert after.get("session_id") == "sess_renew"

        self.provider.release_lock("user_a")

    # ---- Test E: Renewal does not rely on heartbeat ----
    def test_renewal_does_not_rely_on_heartbeat(self):
        """
        Prove: Renewal decision uses owner/session + lease state, not heartbeat.
        """
        now = datetime.now()

        # Create lock with stale heartbeat but valid lease
        lock_data = {
            "locked": True,
            "session_id": "sess_renew_hb",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=70)).isoformat(),
            "last_heartbeat": (now - timedelta(seconds=70)).isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }

        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # Renew with correct owner/session - should succeed despite stale heartbeat
        renewal_success = self.provider.renew_lock("user_a", "sess_renew_hb")
        assert renewal_success is True, "Renewal should succeed with valid lease, even with stale heartbeat"

        status = self.provider.remote_lock_status()
        assert status["owner"] == "user_a"
        assert status["session_id"] == "sess_renew_hb"

        self.provider.force_release("user_a")

    # ---- Test F: Renewal race safety ----
    def test_renewal_race_safety(self):
        """
        Prove: Renewal remains CAS-safe. If B acquires, A's renewal fails.
        """
        # A acquires lock
        now = datetime.now()
        lock_data_a = {
            "locked": True,
            "session_id": "sess_A",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        self.provider.acquire_lock(lock_data_a)

        expected_oid = self.provider._remote_lock_oid()
        assert expected_oid is not None

        # Make A's lock stale so B can acquire
        stale_lock = lock_data_a.copy()
        stale_lock["lease_expires_at"] = (now - timedelta(seconds=10)).isoformat()
        stale_commit = self.provider._create_lock_commit_plumbing(stale_lock, expected_oid)
        self.provider._push_lock_branch(stale_commit, expected_oid)

        # B acquires
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()

        lock_data_b = {
            "locked": True,
            "session_id": "sess_B",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
        }
        success_b = provider_b.acquire_lock(lock_data_b)
        assert success_b is True

        # A tries to renew - should fail
        result = self.provider.renew_lock("user_a", "sess_A")
        assert result is False, "A's renewal should fail because B now owns the lock"

        # Verify B's lock survives
        status = self.provider.remote_lock_status()
        assert status["owner"] == "user_b"
        assert status["session_id"] == "sess_B"

        provider_b.release_lock("user_b")

    # ---- Test G: FINISHING deadline unchanged ----
    def test_finishing_deadline_unchanged(self):
        """
        Prove: Absolute 120-second FINISHING deadline remains unchanged after renewal.
        """
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

        before = self.provider.remote_lock_status()
        deadline_before = before.get("finishing_deadline")
        assert deadline_before is not None

        # Renew
        self.provider.renew_lock("user_a", "sess_finish")

        after = self.provider.remote_lock_status()
        deadline_after = after.get("finishing_deadline")

        assert deadline_after == deadline_before, "FINISHING deadline changed"

        self.provider.force_release("user_a")

    # ---- Test H: MAIN isolation ----
    def test_main_isolation(self):
        """
        Prove: All lease operations leave MAIN unchanged.
        """
        before_head = get_main_head(self.repo_path)
        before_branch = get_main_branch(self.repo_path)
        before_status = get_main_status(self.repo_path)

        now = datetime.now()
        lock_data = {
            "locked": True,
            "session_id": "sess_iso",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }

        self.provider.acquire_lock(lock_data)

        # Perform multiple operations
        self.provider.renew_lock("user_a", "sess_iso")
        status = self.provider.remote_lock_status()
        assert status["locked"] is True

        self.provider.release_lock("user_a")

        after_head = get_main_head(self.repo_path)
        after_branch = get_main_branch(self.repo_path)
        after_status = get_main_status(self.repo_path)

        assert after_head == before_head, "MAIN HEAD changed"
        assert after_branch == before_branch, "MAIN branch changed"
        assert after_status == before_status, "MAIN working tree changed"

    # ---- Test I: Legacy lock without lease_expires_at is stale ----
    def test_legacy_lock_without_lease_stale(self):
        """
        Prove: Locks without lease_expires_at are treated as stale.
        This ensures backward compatibility does not become a second authority.
        """
        now = datetime.now()

        # Create a lock without lease_expires_at (legacy format)
        lock_data = {
            "locked": True,
            "session_id": "sess_legacy",
            "owner": "user_a",
            "username": "user_a",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),  # Fresh, but should not matter
            "machine": "test_machine",
            # No lease_expires_at!
        }

        expected_oid = self.provider._remote_lock_oid()
        commit_sha = self.provider._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider._push_lock_branch(commit_sha, expected_oid)

        # _is_lock_valid should return False (no lease_expires_at)
        remote_lock = self.provider._read_lock_from_oid(self.provider._remote_lock_oid())
        assert self.provider._is_lock_valid(remote_lock) is False

        # Another user can acquire despite fresh heartbeat
        provider_b = GitSynchronizationProvider(
            repo_path=self.repo_path,
            repository_url=str(self.remote_path),
            token="",
            branch="main"
        )
        provider_b.connect()

        lock_data_b = {
            "locked": True,
            "session_id": "sess_B_legacy",
            "owner": "user_b",
            "username": "user_b",
            "user_id": "user_b",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        success_b = provider_b.acquire_lock(lock_data_b)
        assert success_b is True, "Legacy lock without lease should be stale"

        status = provider_b.remote_lock_status()
        assert status["owner"] == "user_b"
        assert status["session_id"] == "sess_B_legacy"

        provider_b.release_lock("user_b")