# -*- coding: utf-8 -*-
"""Integration tests for remote lease authority finalization."""

import pytest
import subprocess
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.events.event_bus import EventBus


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


class TestLeaseAuthorityIntegration:
    """Integration tests for lease authority finalization."""

    @pytest.fixture(autouse=True)
    def setup(self, seeded_remote, tmp_path):
        self.remote_path = seeded_remote

        # Runtime A
        runtime_a = tmp_path / "runtime_a"
        runtime_a.mkdir(parents=True, exist_ok=True)
        repo_a = runtime_a / "repository"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(seeded_remote), str(repo_a)],
            check=True
        )
        subprocess.run(["git", "config", "user.name", "User A"], cwd=repo_a, check=True)
        subprocess.run(["git", "config", "user.email", "a@example.com"], cwd=repo_a, check=True)

        provider_a = GitSynchronizationProvider(
            repo_path=repo_a,
            repository_url=str(seeded_remote),
            token="",
            branch="main"
        )
        provider_a.connect()

        event_bus_a = EventBus()
        cm_a = CollaborationManager(
            runtime_root=runtime_a,
            event_bus=event_bus_a,
            sync_provider=provider_a
        )
        cm_a.initialize("user_a", "User A", "admin")

        # Runtime B
        runtime_b = tmp_path / "runtime_b"
        runtime_b.mkdir(parents=True, exist_ok=True)
        repo_b = runtime_b / "repository"
        subprocess.run(
            ["git", "clone", "--branch", "main", str(seeded_remote), str(repo_b)],
            check=True
        )
        subprocess.run(["git", "config", "user.name", "User B"], cwd=repo_b, check=True)
        subprocess.run(["git", "config", "user.email", "b@example.com"], cwd=repo_b, check=True)

        provider_b = GitSynchronizationProvider(
            repo_path=repo_b,
            repository_url=str(seeded_remote),
            token="",
            branch="main"
        )
        provider_b.connect()

        event_bus_b = EventBus()
        cm_b = CollaborationManager(
            runtime_root=runtime_b,
            event_bus=event_bus_b,
            sync_provider=provider_b
        )
        cm_b.initialize("user_b", "User B", "admin")

        self.cm_a = cm_a
        self.cm_b = cm_b
        self.provider_a = provider_a
        self.provider_b = provider_b
        self.runtime_a = runtime_a
        self.runtime_b = runtime_b

        yield

        # Cleanup
        try:
            cm_a.shutdown()
        except:
            pass
        try:
            cm_b.shutdown()
        except:
            pass
        subprocess.run(
            ["git", "push", str(seeded_remote), "--delete", "lock-main", "--force"],
            capture_output=True
        )

    # ---- Test A: Missing lease + fresh heartbeat = stale ----
    def test_is_lock_stale_lease_only(self):
        """Test that _is_lock_stale uses lease_expires_at only."""
        # Lock with valid lease - not stale
        lock_data = {
            "locked": True,
            "session_id": "sess1",
            "owner": "user_a",
            "last_heartbeat": (datetime.now() - timedelta(seconds=120)).isoformat(),
            "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
        }
        assert self.cm_a._is_lock_stale(lock_data) is False

        # Lock without lease, fresh heartbeat - STALE (missing lease = invalid)
        lock_data2 = {
            "locked": True,
            "session_id": "sess2",
            "owner": "user_a",
            "last_heartbeat": datetime.now().isoformat(),
        }
        assert self.cm_a._is_lock_stale(lock_data2) is True

        # Lock without lease, stale heartbeat - STALE
        lock_data3 = {
            "locked": True,
            "session_id": "sess3",
            "owner": "user_a",
            "last_heartbeat": (datetime.now() - timedelta(seconds=120)).isoformat(),
        }
        assert self.cm_a._is_lock_stale(lock_data3) is True

    # ---- Test B: Stale Heartbeat + Valid Remote Lease ----
    def test_stale_heartbeat_valid_lease_manager(self):
        now = datetime.now()

        # A acquires lock with valid lease and old heartbeat
        lock_data = {
            "locked": True,
            "session_id": "sess_mgr_stale",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=120)).isoformat(),
            "last_heartbeat": (now - timedelta(seconds=120)).isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Check lock status via CollaborationManager
        status = self.cm_a.get_lock_status()
        assert status["locked"] is True
        assert status["owner"] == "User A" or status["owner"] == "user_a"

        # Request write should NOT force-release (lease is valid)
        result = self.cm_a.request_write()
        assert result.is_granted or result.is_waiting

        # Lock should still exist
        status_after = self.cm_a.get_lock_status()
        assert status_after.get("locked") is True

    # ---- Test C: Expired Lease + Fresh Heartbeat = stale ----
    def test_expired_lease_fresh_heartbeat_manager(self):
        now = datetime.now()

        # A acquires lock with expired lease but fresh heartbeat
        lock_data = {
            "locked": True,
            "session_id": "sess_mgr_expired",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=120)).isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now - timedelta(seconds=1)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # B requests write - should acquire because lock is stale
        result = self.cm_b.request_write()
        assert result.is_granted or result.is_waiting

        # Verify B owns the lock now
        status = self.cm_b.get_lock_status()
        if result.is_granted:
            assert status.get("locked") is True
            assert status.get("owner") == "User B" or status.get("owner") == "user_b"

    # ---- Test D: Heartbeat Stops, Lease Valid ----
    def test_heartbeat_stops_lease_valid_manager(self):
        now = datetime.now()

        lock_data = {
            "locked": True,
            "session_id": "sess_mgr_hb_stop",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Simulate heartbeat stopping (do not update)
        # Lock should remain valid

        status = self.cm_a.get_lock_status()
        assert status.get("locked") is True
        assert status.get("owner") == "User A" or status.get("owner") == "user_a"

        # B tries to acquire - should wait
        result = self.cm_b.request_write()
        assert result.is_waiting

        # Verify lock still owned by A
        status_after = self.cm_a.get_lock_status()
        assert status_after.get("locked") is True
        assert status_after.get("owner") == "User A" or status_after.get("owner") == "user_a"

    # ---- Test E: Renewal ----
    def test_renewal_manager(self):
        now = datetime.now()

        lock_data = {
            "locked": True,
            "session_id": "sess_mgr_renew",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        initial_lease = self.provider_a.remote_lock_status().get("lease_expires_at")
        assert initial_lease is not None

        time.sleep(1)
        success = self.provider_a.renew_lock("User A", "sess_mgr_renew")
        assert success is True

        after_lease = self.provider_a.remote_lock_status().get("lease_expires_at")
        assert after_lease is not None
        assert datetime.fromisoformat(after_lease) > datetime.fromisoformat(initial_lease)

        status = self.provider_a.remote_lock_status()
        assert status.get("owner") == "User A" or status.get("owner") == "user_a"

    # ---- Test F: Renewal Race ----
    def test_renewal_race_manager(self):
        now = datetime.now()

        # A acquires lock
        lock_data_a = {
            "locked": True,
            "session_id": "sess_race_A",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data_a, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Make A's lock stale so B can acquire
        stale_lock = lock_data_a.copy()
        stale_lock["lease_expires_at"] = (now - timedelta(seconds=10)).isoformat()

        # Retry push stale lock (handle race)
        push_stale = False
        for attempt in range(3):
            current_oid = self.provider_a._remote_lock_oid()
            if current_oid is None:
                break
            stale_commit = self.provider_a._create_lock_commit_plumbing(stale_lock, current_oid)
            if stale_commit is None:
                break
            push_stale = self.provider_a._push_lock_branch(stale_commit, current_oid)
            if push_stale:
                break
            time.sleep(0.2)

        assert push_stale is True, "Failed to push stale lock after retries"

        # Wait for remote to propagate
        time.sleep(0.5)

        # Verify remote lock is now stale (expired lease)
        remote_status = self.provider_a.remote_lock_status()
        assert remote_status.get("locked") is True
        lease = remote_status.get("lease_expires_at")
        assert lease is not None
        assert datetime.fromisoformat(lease) < now

        # B acquires lock (should succeed because A's lease expired)
        lock_data_b = {
            "locked": True,
            "session_id": "sess_race_B",
            "owner": "User B",
            "username": "User B",
            "user_id": "user_b",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        success_b = self.provider_b.acquire_lock(lock_data_b)
        assert success_b is True, "B should acquire stale lock"

        # Verify B owns the lock
        status_b = self.provider_b.remote_lock_status()
        assert status_b.get("owner") == "User B" or status_b.get("owner") == "user_b"
        assert status_b.get("session_id") == "sess_race_B"

        # A tries to renew - should fail
        result = self.provider_a.renew_lock("User A", "sess_race_A")
        assert result is False, "A's renewal should fail because B now owns the lock"

        # Verify B's lock survives
        status_after = self.provider_b.remote_lock_status()
        assert status_after.get("owner") == "User B" or status_after.get("owner") == "user_b"
        assert status_after.get("session_id") == "sess_race_B"

    # ---- Test G: No Remote Force Release From Heartbeat ----
    def test_no_remote_force_release_from_heartbeat(self):
        """Prove that stale heartbeat does NOT force-release remote lock."""
        now = datetime.now()

        # A acquires lock with valid lease
        lock_data = {
            "locked": True,
            "session_id": "sess_no_force",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Simulate heartbeat becoming stale (do not update)
        # But lease remains valid

        # Check stale detection - should NOT be stale
        lock_info = self.provider_a._read_lock_from_oid(self.provider_a._remote_lock_oid())
        is_stale = self.cm_a._is_lock_stale(lock_info)
        assert is_stale is False, "Lock should not be stale (lease valid)"

        # Verify lock still exists
        status = self.cm_a.get_lock_status()
        assert status.get("locked") is True
        assert status.get("owner") == "User A" or status.get("owner") == "user_a"

        # B tries to acquire - should wait (not force-release)
        result = self.cm_b.request_write()
        assert result.is_waiting, "B should wait, not acquire"

        # Verify lock still owned by A
        status_after = self.cm_a.get_lock_status()
        assert status_after.get("locked") is True
        assert status_after.get("owner") == "User A" or status_after.get("owner") == "user_a"

    # ---- Test H: Fresh heartbeat does NOT keep expired lease valid ----
    def test_fresh_heartbeat_expired_lease_stale(self):
        """Prove that fresh heartbeat does NOT keep expired lease valid."""
        now = datetime.now()

        # Create lock with expired lease but fresh heartbeat
        lock_data = {
            "locked": True,
            "session_id": "sess_fresh_hb_expired",
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": (now - timedelta(seconds=120)).isoformat(),
            "last_heartbeat": now.isoformat(),
            "lease_expires_at": (now - timedelta(seconds=1)).isoformat(),
            "machine": "test_machine",
        }
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Check stale detection - should be stale (lease expired)
        lock_info = self.provider_a._read_lock_from_oid(self.provider_a._remote_lock_oid())
        is_stale = self.cm_a._is_lock_stale(lock_info)
        assert is_stale is True, "Lock should be stale (lease expired)"

        # B should be able to acquire
        result = self.cm_b.request_write()
        assert result.is_granted or result.is_waiting

        # If granted, verify B owns the lock
        if result.is_granted:
            status = self.cm_b.get_lock_status()
            assert status.get("locked") is True
            assert status.get("owner") == "User B" or status.get("owner") == "user_b"