# -*- coding: utf-8 -*-
"""Tests for collaboration waiting user visibility and auto-grant."""

import pytest
import time
import subprocess
from pathlib import Path

from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.write_queue import WriteQueue
from centermanager.events.event_bus import EventBus
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState


@pytest.fixture
def temp_collab(tmp_path):
    """Create collaboration manager with temp runtime."""
    event_bus = EventBus()
    cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
    cm.initialize("user_a", "User A", "admin")
    return cm


def test_get_waiting_users_empty(temp_collab):
    """No waiting users when queue empty."""
    waiting = temp_collab.get_waiting_users()
    assert waiting == []


def test_get_waiting_users_after_request(temp_collab):
    """Waiting users appear after request."""
    temp_collab.request_write()

    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()
    time.sleep(0.5)

    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 1
    assert any(w["username"] == "User B" for w in waiting)


def test_waiting_users_after_release(temp_collab):
    """Waiting list clears after writer releases and next auto-acquires."""
    # A acquires lock
    temp_collab.request_write()
    assert temp_collab.is_writing() is True

    # B requests (enters queue)
    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()
    time.sleep(0.5)

    # Verify B is waiting
    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 1
    assert any(w["username"] == "User B" for w in waiting)

    # A releases lock
    temp_collab.release_write()
    time.sleep(1.0)

    # B should auto-acquire via is_next_eligible polling
    if cm_b.is_next_eligible():
        cm_b.request_write()

    time.sleep(0.5)

    # B should now be writing
    assert cm_b.is_writing() is True

    # A checks waiting list - B should not be in waiting list
    waiting = temp_collab.get_waiting_users()
    assert all(w["username"] != "User B" for w in waiting)


def test_get_waiting_users_multiple(temp_collab):
    """Multiple waiting users appear correctly."""
    temp_collab.request_write()

    cm_b = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_b.initialize("user_b", "User B", "teacher")
    cm_b.request_write()

    cm_c = CollaborationManager(
        runtime_root=temp_collab._runtime_root,
        event_bus=EventBus()
    )
    cm_c.initialize("user_c", "User C", "teacher")
    cm_c.request_write()

    time.sleep(0.5)

    waiting = temp_collab.get_waiting_users()
    assert len(waiting) >= 2
    usernames = [w["username"] for w in waiting]
    assert "User B" in usernames
    assert "User C" in usernames


def test_auto_grant_waiting_request_local(tmp_path):
    """
    Test that a waiting request is automatically granted when lock becomes free.
    Uses local lock (no sync_provider) for deterministic testing.
    """
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    # Machine A acquires lock
    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    result = cm_a.request_write()
    assert result.is_granted

    # Machine B requests lock -> WAITING
    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b.initialize("user_b", "User B", "admin")
    result = cm_b.request_write()
    assert result.is_waiting

    # Verify B is waiting
    queue = cm_b.get_queue()
    assert queue["length"] == 1
    request = queue["requests"][0]
    assert request["username"] == "User B"

    # A releases lock
    cm_a.release_write()

    # B should auto-grant
    success = cm_b.grant_existing_waiting_request()
    assert success, "grant_existing_waiting_request should succeed"
    assert cm_b.is_writing(), "B should be writing"
    queue = cm_b.get_queue()
    assert queue["length"] == 0, "Queue should be empty after grant"
    lock_status = cm_b.get_lock_status()
    assert lock_status.get("locked") is True, "Lock should be held by B"
    assert lock_status.get("owner") == "User B" or lock_status.get("owner") == cm_b._session.username

    # Cleanup
    cm_b.release_write()
    cm_a.shutdown()
    cm_b.shutdown()


def test_no_duplicate_requests(tmp_path):
    """Test that requesting write multiple times while waiting does not create duplicate queue entries."""
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    # A acquires lock
    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    cm_a.request_write()

    # B requests -> WAITING
    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b.initialize("user_b", "User B", "admin")
    result = cm_b.request_write()
    assert result.is_waiting

    # B requests again (should not create new request)
    result2 = cm_b.request_write()
    assert result2.is_waiting
    assert result2.request_id == result.request_id

    queue = cm_b.get_queue()
    assert queue["length"] == 1

    cm_a.release_write()
    cm_a.shutdown()
    cm_b.shutdown()


def test_fifo_ordering(tmp_path):
    """Test that waiting queue processes requests in FIFO order."""
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    # A acquires lock
    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    cm_a.request_write()

    # B, C, D request
    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b.initialize("user_b", "User B", "admin")
    cm_b.request_write()

    cm_c = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_c.initialize("user_c", "User C", "admin")
    cm_c.request_write()

    cm_d = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_d.initialize("user_d", "User D", "admin")
    cm_d.request_write()

    # A releases
    cm_a.release_write()

    # B should be granted first
    success_b = cm_b.grant_existing_waiting_request()
    assert success_b
    assert cm_b.is_writing()
    cm_b.release_write()

    # Then C
    success_c = cm_c.grant_existing_waiting_request()
    assert success_c
    assert cm_c.is_writing()
    cm_c.release_write()

    # Then D
    success_d = cm_d.grant_existing_waiting_request()
    assert success_d
    assert cm_d.is_writing()
    cm_d.release_write()

    cm_a.shutdown()
    cm_b.shutdown()
    cm_c.shutdown()
    cm_d.shutdown()


def test_a_does_not_acquire_for_b(tmp_path):
    """
    Test that when A releases lock, A does NOT acquire lock on behalf of B.
    This verifies the ownership semantics: B must self-acquire.
    """
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()

    # A acquires lock
    cm_a = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_a.initialize("user_a", "User A", "admin")
    result_a = cm_a.request_write()
    assert result_a.is_granted

    # B requests -> WAITING
    cm_b = CollaborationManager(runtime_root=runtime_root, event_bus=event_bus, sync_provider=None)
    cm_b.initialize("user_b", "User B", "admin")
    result_b = cm_b.request_write()
    assert result_b.is_waiting

    # Verify B is waiting
    queue_b = cm_b.get_queue()
    assert queue_b["length"] == 1
    request = queue_b["requests"][0]
    assert request["username"] == "User B"

    # A releases lock - must NOT acquire for B
    cm_a.release_write()
    assert not cm_a.is_writing()
    assert cm_a.get_lock_owner() is None

    # Lock should be free (not held by A, not held by B)
    lock_status = cm_a.get_lock_status()
    assert lock_status.get("locked") is False, "Lock should be free after A releases"

    # B should still be waiting and not writing
    assert not cm_b.is_writing()

    # Cleanup
    cm_a.shutdown()
    cm_b.shutdown()


# ===== Cross-machine tests =====

def test_cross_machine_auto_grant_with_separate_runtimes(tmp_path):
    """
    Cross-machine test: A holds lock, B waits, A releases, B auto-grants.
    Uses separate runtime directories and a real bare remote.
    """
    import subprocess
    import json
    from datetime import datetime
    from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider

    # Create a seeded remote repository
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

    # ---- Machine A ----
    runtime_a = tmp_path / "runtime_a"
    runtime_a.mkdir(parents=True, exist_ok=True)

    repo_a_path = runtime_a / "repository"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote_path), str(repo_a_path)],
        check=True
    )

    subprocess.run(
        ["git", "config", "user.name", "Test User A"],
        cwd=repo_a_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test_a@example.com"],
        cwd=repo_a_path,
        check=True,
    )

    provider_a = GitSynchronizationProvider(
        repo_path=repo_a_path,
        repository_url=str(remote_path),
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

    # ---- Machine B ----
    runtime_b = tmp_path / "runtime_b"
    runtime_b.mkdir(parents=True, exist_ok=True)

    repo_b_path = runtime_b / "repository"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote_path), str(repo_b_path)],
        check=True
    )

    subprocess.run(
        ["git", "config", "user.name", "Test User B"],
        cwd=repo_b_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test_b@example.com"],
        cwd=repo_b_path,
        check=True,
    )

    provider_b = GitSynchronizationProvider(
        repo_path=repo_b_path,
        repository_url=str(remote_path),
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

    # ---- Test flow with debug ----
    print("\n=== TEST DEBUG ===\n")

    # A acquires lock
    result_a = cm_a.request_write()
    print(f"A result: {result_a.is_granted}, {result_a.is_waiting}")
    assert result_a.is_granted, "A should acquire lock"
    assert cm_a.is_writing()

    # Capture remote state after A
    ls = subprocess.run(["git", "ls-remote", str(remote_path), "refs/heads/lock-main"], capture_output=True, text=True)
    print(f"REMOTE lock-main after A: {ls.stdout.strip()}")
    assert ls.stdout.strip() != "", "Remote lock should exist after A"

    # Capture A HEAD
    head_a = subprocess.run(["git", "branch", "--show-current"], cwd=repo_a_path, capture_output=True, text=True)
    print(f"A HEAD: {head_a.stdout.strip()}")
    assert head_a.stdout.strip() == "main", f"A HEAD should be main, got {head_a.stdout.strip()}"

    # B requests lock -> WAITING
    result_b = cm_b.request_write()
    print(f"B result: {result_b.is_granted}, {result_b.is_waiting}")
    assert result_b.is_waiting, f"B should be waiting, got {result_b.is_waiting}"
    assert not cm_b.is_writing()

    # Capture remote state after B
    ls2 = subprocess.run(["git", "ls-remote", str(remote_path), "refs/heads/lock-main"], capture_output=True, text=True)
    print(f"REMOTE lock-main after B: {ls2.stdout.strip()}")

    # Verify B is in queue
    queue_b = cm_b.get_queue()
    assert queue_b["length"] == 1
    request = queue_b["requests"][0]
    assert request["username"] == "User B"

    # A releases lock
    cm_a.release_write()
    assert not cm_a.is_writing()
    assert cm_a.get_lock_owner() is None

    # Capture remote state after A release
    ls3 = subprocess.run(["git", "ls-remote", str(remote_path), "refs/heads/lock-main"], capture_output=True, text=True)
    print(f"REMOTE lock-main after A release: {ls3.stdout.strip()}")
    # Remote should be free
    assert ls3.stdout.strip() == "", "Remote lock should be deleted after A release"

    # Give remote time to propagate
    time.sleep(5)

    # B grants existing waiting request
    granted = cm_b.grant_existing_waiting_request()
    print(f"B grant result: {granted}")
    assert granted, "B should auto-grant"

    assert cm_b.is_writing()

    # Verify B's request was consumed
    queue_b = cm_b.get_queue()
    assert queue_b["length"] == 0

    # Verify remote owner is B
    lock_status = cm_b.get_lock_status()
    assert lock_status.get("locked") is True
    assert lock_status.get("owner") == "User B" or lock_status.get("session_id") == cm_b._session.session_id

    # Cleanup
    cm_b.release_write()
    cm_a.shutdown()
    cm_b.shutdown()