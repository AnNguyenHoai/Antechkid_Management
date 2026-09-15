# -*- coding: utf-8 -*-
"""Remote request_write CAS safety tests with real bare Git remote.
Strengthened: explicitly proves local mirror stale cannot delete new remote lock.
"""

import pytest
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.synchronization import GitSynchronizationProvider


# ---- Helpers ----

def get_remote_lock_oid(remote_path: Path) -> str:
    """Get OID of remote lock-main branch, or None if not exist."""
    result = subprocess.run(
        ["git", "ls-remote", str(remote_path), "refs/heads/lock-main"],
        capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.split()[0]


def get_remote_lock_data(remote_path: Path, oid: str) -> dict:
    """Get lock.json content from remote OID."""
    if oid is None:
        return None
    try:
        content = subprocess.check_output(
            ["git", "show", f"{oid}:lock.json"],
            cwd=str(remote_path),
            text=True
        )
        return json.loads(content)
    except Exception:
        return None


def read_local_lock(cm) -> dict:
    """Read local lock.json content from CollaborationManager."""
    lock_path = cm._collab_dir / "lock.json"
    if not lock_path.exists():
        return {}
    with open(lock_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_local_lock(cm, data):
    """Write lock data directly to local lock.json."""
    lock_path = cm._collab_dir / "lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def clean_remote_lock(remote_path: Path):
    """Delete remote lock-main branch if exists."""
    subprocess.run(
        ["git", "push", str(remote_path), "--delete", "lock-main", "--force"],
        capture_output=True, check=False
    )


def create_machine(tmp_path: Path, remote_path: Path, name: str, branch: str = "main"):
    """Create a machine (runtime + repo + provider + collab manager)."""
    runtime_root = tmp_path / f"runtime_{name}"
    runtime_root.mkdir(parents=True, exist_ok=True)
    repo_path = runtime_root / "repository"

    # Clone from remote
    subprocess.run(
        ["git", "clone", "--branch", branch, str(remote_path), str(repo_path)],
        check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", f"User {name}"],
        cwd=repo_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", f"{name}@example.com"],
        cwd=repo_path, check=True, capture_output=True
    )

    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=str(remote_path),
        token="",
        branch=branch
    )
    provider.connect()

    event_bus = EventBus()
    cm = CollaborationManager(
        runtime_root=runtime_root,
        event_bus=event_bus,
        sync_provider=provider
    )
    cm.initialize(f"user_{name}", f"User {name}", "admin")

    return cm, provider, runtime_root, repo_path


# ---- Tests ----

def test_stale_local_mirror_vs_new_remote_owner(seeded_center_manager_remote, tmp_path):
    """
    Critical Test A & B:
    - Explicitly create A local mirror stale X.
    - B acquires new valid remote Y.
    - A.request_write() must NOT force_release Y.
    - Remote Y survives, owner = B.
    """
    remote_path = seeded_center_manager_remote

    # Clean any stale lock from previous tests
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")
    cm_b, provider_b, _, _ = create_machine(tmp_path, remote_path, "B")

    # Force release local/remote stale locks (if any)
    provider_a.force_release("User A")
    provider_b.force_release("User B")

    # ---- Step 1: Create local mirror X (stale) ----
    past = datetime.now() - timedelta(seconds=60)
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": past.isoformat(),
        "last_heartbeat": past.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (past + timedelta(seconds=10)).isoformat(),
        "lock_generation": 0,
        "lease_revision": 0,
        "finishing_started_at": None,
        "finishing_deadline": None,
        "publish_intent": False,
    }
    write_local_lock(cm_a, lock_data_a)

    # Verify local mirror X is stale
    local_lock = read_local_lock(cm_a)
    assert local_lock.get("locked") is True
    assert local_lock.get("owner") == "User A"
    assert local_lock.get("session_id") == cm_a._session.session_id
    assert cm_a._is_lock_stale(local_lock) is True

    # ---- Step 2: Create remote X (stale) ----
    expected_oid = provider_a._remote_lock_oid()
    commit_sha = provider_a._create_lock_commit_plumbing(lock_data_a, expected_oid)
    assert commit_sha is not None
    assert provider_a._push_lock_branch(commit_sha, expected_oid)

    # Verify remote X
    oid_x = get_remote_lock_oid(remote_path)
    data_x = get_remote_lock_data(remote_path, oid_x)
    assert data_x is not None
    assert data_x.get("owner") == "User A"
    assert data_x.get("session_id") == cm_a._session.session_id

    # ---- Step 3: B acquires valid remote Y ----
    now = datetime.now()
    lock_data_b = {
        "locked": True,
        "session_id": cm_b._session.session_id,
        "owner": cm_b._session.username,
        "username": cm_b._session.username,
        "user_id": cm_b._session.user_id,
        "acquired_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
        "machine": "machineB",
        "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
        "lock_generation": 0,
        "lease_revision": 0,
        "finishing_started_at": None,
        "finishing_deadline": None,
        "publish_intent": False,
    }
    assert provider_b.acquire_lock(lock_data_b), "B should acquire lock"

    # Verify remote Y
    oid_y = get_remote_lock_oid(remote_path)
    data_y = get_remote_lock_data(remote_path, oid_y)
    assert data_y is not None
    assert data_y.get("owner") == "User B"
    assert data_y.get("session_id") == cm_b._session.session_id

    # ---- Step 4: Verify split state (local A stale X, remote B valid Y) ----
    local_lock_after_b = read_local_lock(cm_a)
    assert cm_a._is_lock_stale(local_lock_after_b) is True
    assert local_lock_after_b.get("session_id") == cm_a._session.session_id

    # Verify remote directly (not via provider cache)
    oid_check = get_remote_lock_oid(remote_path)
    data_check = get_remote_lock_data(remote_path, oid_check)
    assert data_check is not None
    assert data_check.get("locked") is True
    assert data_check.get("owner") == "User B"
    assert data_check.get("session_id") == cm_b._session.session_id

    # ---- Step 5: A.request_write() ----
    with patch.object(cm_a, '_force_release_lock') as mock_force:
        result = cm_a.request_write()
        # B holds valid remote lock, so A must wait
        assert result.is_waiting
        mock_force.assert_not_called()

    # ---- Step 6: Verify Y survives ----
    oid_after = get_remote_lock_oid(remote_path)
    data_after = get_remote_lock_data(remote_path, oid_after)
    assert data_after is not None
    assert data_after.get("owner") == "User B"
    assert data_after.get("session_id") == cm_b._session.session_id
    assert oid_after == oid_y


def test_expired_remote_lease_acquisition(seeded_center_manager_remote, tmp_path):
    """Critical Test C: Expired remote lease can be safely replaced via acquire_lock()."""
    remote_path = seeded_center_manager_remote
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")
    cm_b, provider_b, _, _ = create_machine(tmp_path, remote_path, "B")

    provider_a.force_release("User A")
    provider_b.force_release("User B")

    # A creates an expired lock using plumbing
    past = datetime.now() - timedelta(seconds=60)
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": past.isoformat(),
        "last_heartbeat": past.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (past + timedelta(seconds=10)).isoformat(),
        "lock_generation": 0,
        "lease_revision": 0,
        "finishing_started_at": None,
        "finishing_deadline": None,
        "publish_intent": False,
    }
    expected_oid = provider_a._remote_lock_oid()
    commit_sha = provider_a._create_lock_commit_plumbing(lock_data_a, expected_oid)
    assert commit_sha is not None
    assert provider_a._push_lock_branch(commit_sha, expected_oid)

    # Verify remote lock exists with A
    oid = get_remote_lock_oid(remote_path)
    data = get_remote_lock_data(remote_path, oid)
    assert data is not None
    assert data.get("owner") == "User A"

    # B requests write – should acquire (expired)
    result = cm_b.request_write()
    assert result.is_granted, "B should acquire expired lock"
    assert cm_b.is_writing, "B should be writing"

    # Verify remote owner B
    oid_after = get_remote_lock_oid(remote_path)
    data_after = get_remote_lock_data(remote_path, oid_after)
    assert data_after.get("owner") == "User B"
    assert data_after.get("session_id") == cm_b._session.session_id


def test_valid_other_owner(seeded_center_manager_remote, tmp_path):
    """Critical Test D: Valid remote lock owned by another machine must remain untouched."""
    remote_path = seeded_center_manager_remote
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")
    cm_b, provider_b, _, _ = create_machine(tmp_path, remote_path, "B")

    provider_a.force_release("User A")
    provider_b.force_release("User B")

    # A acquires valid lock (lease future)
    now = datetime.now()
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
    }
    assert provider_a.acquire_lock(lock_data_a)

    # B requests write – must wait, not acquire
    with patch.object(cm_b, '_force_release_lock') as mock_force:
        result = cm_b.request_write()
        assert result.is_waiting, "B should wait because A holds valid lock"
        mock_force.assert_not_called()

    # Remote still A
    oid = get_remote_lock_oid(remote_path)
    data = get_remote_lock_data(remote_path, oid)
    assert data.get("owner") == "User A"
    assert data.get("session_id") == cm_a._session.session_id


def test_stale_heartbeat_valid_lease(seeded_center_manager_remote, tmp_path):
    """Critical Test E: Stale local heartbeat does NOT affect remote lock when lease valid."""
    remote_path = seeded_center_manager_remote
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")

    provider_a.force_release("User A")

    # A acquires valid lock
    now = datetime.now()
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
    }
    assert provider_a.acquire_lock(lock_data_a)

    # Create local lock by requesting write (will be granted)
    result = cm_a.request_write()
    assert result.is_granted, "A should be granted write"

    # Stale local heartbeat (modify lock.json directly)
    lock_path = cm_a._collab_dir / "lock.json"
    with open(lock_path, 'r') as f:
        data = json.load(f)
    old_hb = (datetime.now() - timedelta(seconds=70)).isoformat()
    data["last_heartbeat"] = old_hb
    with open(lock_path, 'w') as f:
        json.dump(data, f)

    # Verify local lock exists and remote lease remains valid.
    # In remote mode, _is_lock_stale only checks lease_expires_at, not heartbeat.
    # So the lock should NOT be considered stale.
    local_lock = read_local_lock(cm_a)
    assert local_lock.get("locked") is True
    # Remote lease is still valid, so stale check should return False.
    assert cm_a._is_lock_stale(local_lock) is False

    # request_write should still be granted because remote lease valid
    with patch.object(cm_a, '_force_release_lock') as mock_force:
        result2 = cm_a.request_write()
        assert result2.is_granted, "A should be granted because remote lease valid"
        mock_force.assert_not_called()

    # Remote lock still exists with A
    oid = get_remote_lock_oid(remote_path)
    data_remote = get_remote_lock_data(remote_path, oid)
    assert data_remote.get("owner") == "User A"
    assert data_remote.get("session_id") == cm_a._session.session_id


def test_release_cas_race(seeded_center_manager_remote, tmp_path):
    """Test F: Release CAS race – safe failure, Y survives."""
    remote_path = seeded_center_manager_remote
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")
    cm_b, provider_b, _, _ = create_machine(tmp_path, remote_path, "B")

    provider_a.force_release("User A")
    provider_b.force_release("User B")

    # A acquires expired lock
    past = datetime.now() - timedelta(seconds=60)
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": past.isoformat(),
        "last_heartbeat": past.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (past + timedelta(seconds=10)).isoformat(),
    }
    expected_oid = provider_a._remote_lock_oid()
    commit_sha = provider_a._create_lock_commit_plumbing(lock_data_a, expected_oid)
    assert commit_sha is not None
    assert provider_a._push_lock_branch(commit_sha, expected_oid)

    # B acquires (replaces)
    now = datetime.now()
    lock_data_b = {
        "locked": True,
        "session_id": cm_b._session.session_id,
        "owner": cm_b._session.username,
        "username": cm_b._session.username,
        "user_id": cm_b._session.user_id,
        "acquired_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
        "machine": "machineB",
        "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
    }
    assert provider_b.acquire_lock(lock_data_b)

    # A tries to release – should fail safely
    result = provider_a.release_lock("User A")
    assert result is False, "A's release should fail because lock owner changed"

    # Verify remote still B
    oid = get_remote_lock_oid(remote_path)
    data = get_remote_lock_data(remote_path, oid)
    assert data.get("owner") == "User B"
    assert data.get("session_id") == cm_b._session.session_id


def test_renewal_cas_race(seeded_center_manager_remote, tmp_path):
    """Test G: Renewal CAS race – safe failure, Y survives."""
    remote_path = seeded_center_manager_remote
    clean_remote_lock(remote_path)

    cm_a, provider_a, _, _ = create_machine(tmp_path, remote_path, "A")
    cm_b, provider_b, _, _ = create_machine(tmp_path, remote_path, "B")

    provider_a.force_release("User A")
    provider_b.force_release("User B")

    # A acquires expired lock
    past = datetime.now() - timedelta(seconds=60)
    lock_data_a = {
        "locked": True,
        "session_id": cm_a._session.session_id,
        "owner": cm_a._session.username,
        "username": cm_a._session.username,
        "user_id": cm_a._session.user_id,
        "acquired_at": past.isoformat(),
        "last_heartbeat": past.isoformat(),
        "machine": "machineA",
        "lease_expires_at": (past + timedelta(seconds=10)).isoformat(),
    }
    expected_oid = provider_a._remote_lock_oid()
    commit_sha = provider_a._create_lock_commit_plumbing(lock_data_a, expected_oid)
    assert commit_sha is not None
    assert provider_a._push_lock_branch(commit_sha, expected_oid)

    # B acquires (replaces)
    now = datetime.now()
    lock_data_b = {
        "locked": True,
        "session_id": cm_b._session.session_id,
        "owner": cm_b._session.username,
        "username": cm_b._session.username,
        "user_id": cm_b._session.user_id,
        "acquired_at": now.isoformat(),
        "last_heartbeat": now.isoformat(),
        "machine": "machineB",
        "lease_expires_at": (now + timedelta(seconds=60)).isoformat(),
    }
    assert provider_b.acquire_lock(lock_data_b)

    # A tries to renew – should fail
    result = provider_a.renew_lock("User A", cm_a._session.session_id)
    assert result is False, "A's renewal should fail because lock owner changed"

    # Verify remote still B
    oid = get_remote_lock_oid(remote_path)
    data = get_remote_lock_data(remote_path, oid)
    assert data.get("owner") == "User B"
    assert data.get("session_id") == cm_b._session.session_id