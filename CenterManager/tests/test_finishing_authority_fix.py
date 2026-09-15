# -*- coding: utf-8 -*-
"""Tests for FINISHING authority respecting remote lease."""

import pytest
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
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


class TestFinishingAuthorityFix:
    """Tests for FINISHING authority respecting remote lease."""

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

        self.cm_a = cm_a
        self.provider_a = provider_a
        self.runtime_a = runtime_a

        yield

        # Cleanup
        try:
            cm_a.shutdown()
        except:
            pass
        subprocess.run(
            ["git", "push", str(seeded_remote), "--delete", "lock-main", "--force"],
            capture_output=True
        )

    # ---- Test A: FINISHING + Expired Remote Lease ----
    def test_finishing_expired_lease_invalid(self):
        """Test that expired remote lease invalidates authority even during FINISHING."""
        now = datetime.now()
        session = self.cm_a.get_session()

        # Create lock with finishing data but expired lease
        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now - timedelta(seconds=10)).isoformat(),  # EXPIRED
            "finishing_started_at": now.isoformat(),
            "finishing_deadline": (now + timedelta(seconds=120)).isoformat(),  # Valid
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
        }

        # Push lock to remote
        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # Sync local lock
        self.cm_a._sync_local_lock()

        # Validate authority - should be INVALID (lease expired)
        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is False
        assert auth["lease_valid"] is False
        assert "lease" in auth["reason"].lower() or "stale" in auth["reason"].lower()

    # ---- Test B: FINISHING + Valid Remote Lease ----
    def test_finishing_valid_lease_valid(self):
        """Test that valid lease + valid finishing deadline = valid authority."""
        now = datetime.now()
        session = self.cm_a.get_session()

        # Create lock with finishing data and valid lease
        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),  # Valid
            "finishing_started_at": now.isoformat(),
            "finishing_deadline": (now + timedelta(seconds=120)).isoformat(),  # Valid
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        self.cm_a._sync_local_lock()

        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is True
        assert auth["lease_valid"] is True

    # ---- Test C: FINISHING Deadline Expired ----
    def test_finishing_deadline_expired_invalid(self):
        now = datetime.now()
        session = self.cm_a.get_session()

        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "finishing_started_at": (now - timedelta(seconds=130)).isoformat(),
            "finishing_deadline": (now - timedelta(seconds=10)).isoformat(),
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        # CRITICAL: Sync local lock from remote
        self.cm_a._sync_local_lock()

        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is False
        assert "deadline expired" in auth["reason"].lower()

    # ---- Test D: EDITING + Valid Lease ----
    def test_editing_valid_lease_valid(self):
        """Test that valid lease in normal EDITING mode = valid authority."""
        now = datetime.now()
        session = self.cm_a.get_session()

        # Create lock with valid lease, no finishing
        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        self.cm_a._sync_local_lock()

        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is True
        assert auth["lease_valid"] is True

    # ---- Test E: EDITING + Expired Lease ----
    def test_editing_expired_lease_invalid(self):
        """Test that expired lease invalidates authority in normal EDITING mode."""
        now = datetime.now()
        session = self.cm_a.get_session()

        # Create lock with expired lease, no finishing
        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now - timedelta(seconds=10)).isoformat(),  # EXPIRED
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        self.cm_a._sync_local_lock()

        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is False
        assert auth["lease_valid"] is False

    # ---- Test F: Missing Lease ----
    def test_missing_lease_invalid(self):
        """Test that missing lease invalidates authority even with finishing deadline."""
        now = datetime.now()
        session = self.cm_a.get_session()

        # Create lock without lease, with finishing data
        lock_data = {
            "locked": True,
            "session_id": session.session_id,
            "owner": "User A",
            "username": "User A",
            "user_id": "user_a",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            # NO lease_expires_at
            "finishing_started_at": now.isoformat(),
            "finishing_deadline": (now + timedelta(seconds=120)).isoformat(),
            "publish_intent": True,
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        self.cm_a._sync_local_lock()

        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is False
        assert "lease" in auth["reason"].lower() or "stale" in auth["reason"].lower()

    # ---- Test G: Owner Mismatch ----
    def test_owner_mismatch_invalid(self):
        """Test that owner mismatch invalidates authority."""
        now = datetime.now()

        # Create lock owned by someone else
        lock_data = {
            "locked": True,
            "session_id": "session_other",
            "owner": "User Other",
            "username": "User Other",
            "user_id": "user_other",
            "acquired_at": now.isoformat(),
            "last_heartbeat": now.isoformat(),
            "machine": "test_machine",
            "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
            "lock_generation": 0,
            "lease_revision": 0,
        }

        expected_oid = self.provider_a._remote_lock_oid()
        commit_sha = self.provider_a._create_lock_commit_plumbing(lock_data, expected_oid)
        self.provider_a._push_lock_branch(commit_sha, expected_oid)

        self.cm_a._sync_local_lock()

        # Validate with User A session - should fail (owner mismatch)
        session = self.cm_a.get_session()
        auth = self.cm_a.validate_write_authority(session)
        assert auth["valid"] is False
        assert "owner" in auth["reason"].lower() or "mismatch" in auth["reason"].lower()