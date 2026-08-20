# -*- coding: utf-8 -*-
"""
TASK 3.3.3-A — Remote Waiting Visibility Contract

Proves remote lock, lease, and release visibility across two independent
clients via the real CollaborationPoller and a shared bare Git remote.
Remote queue visibility is intentionally deferred because WriteQueue is
currently local runtime state.

No UI, no queue redesign, no lock protocol changes.
"""

import pytest
import time
import threading
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QTimer, QEventLoop
from PySide6.QtTest import QSignalSpy, QTest

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import (
    CollaborationManager,
    CollaborationPoller,
    PollerMode,
)
from centermanager.platform.synchronization import GitSynchronizationProvider


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def wait_for_signal(spy, timeout_ms=5000):
    """Wait using the Qt event loop; compatible with PySide6 QSignalSpy."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if spy.count() > 0:
            return True
        QTest.qWait(20)
    return spy.count() > 0



def stop_poller_for_git_mutation(poller):
    """Prevent concurrent Git operations on the same local repository."""
    poller.stop()
    thread = getattr(poller, "_thread", None)
    if thread is not None:
        thread.wait(5000)
        assert not thread.isRunning(), "Poller thread did not stop before Git mutation"


def wait_for_poll(poller, timeout_ms=5000):
    """Request a refresh and wait for the cycle-completion boundary."""
    spy = QSignalSpy(poller.poll_completed)
    poller.request_refresh("test")
    return wait_for_signal(spy, timeout_ms)

def safe_stop_poller(poller, timeout_ms=5000):
    """Safely stop poller and wait for thread to finish."""
    poller.stop()
    if not poller._thread.wait(timeout_ms):
        poller._thread.quit()
        if not poller._thread.wait(2000):
            raise RuntimeError("Poller thread did not stop gracefully")
    assert not poller._thread.isRunning(), "Thread should have stopped"


def wait_for_timer(poller, timeout_ms=2000):
    """Wait until poller._timer is not None."""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if poller._timer is not None:
            return True
        QTest.qWait(50)
    return False


def create_seeded_remote(tmp_path):
    """Create a bare Git remote with initial CenterManager structure."""
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


def create_client(tmp_path, remote_path, name, lease_duration_seconds=None):
    """
    Create an independent collaboration client with its own runtime,
    repository, provider, CollaborationManager, and Poller.
    """
    runtime_root = tmp_path / f"runtime_{name}"
    runtime_root.mkdir(parents=True, exist_ok=True)

    repo_path = runtime_root / "repository"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(remote_path), str(repo_path)],
        capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", f"User {name}"],
        cwd=repo_path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.email", f"{name}@example.com"],
        cwd=repo_path, capture_output=True, check=True
    )

    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=str(remote_path),
        token="",
        branch="main"
    )
    if lease_duration_seconds is not None:
        provider._lease_duration_seconds = lease_duration_seconds
    provider.connect()

    event_bus = EventBus()
    cm = CollaborationManager(
        runtime_root=runtime_root,
        event_bus=event_bus,
        sync_provider=provider,
        lock_timeout=lease_duration_seconds if lease_duration_seconds is not None else 60,
    )
    cm.initialize(f"user_{name}", f"User {name}", "admin")

    poller = CollaborationPoller(cm, event_bus, normal_interval=2, waiting_interval=1)

    return {
        "runtime_root": runtime_root,
        "repo_path": repo_path,
        "provider": provider,
        "cm": cm,
        "poller": poller,
        "event_bus": event_bus,
        "name": name,
    }


def start_client(client):
    """Start poller and wait for timer."""
    client["poller"].start()
    assert wait_for_timer(client["poller"], timeout_ms=2000), f"{client['name']} timer not created"


def stop_client(client):
    """Stop poller safely."""
    safe_stop_poller(client["poller"])


def get_main_head(repo_path):
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, text=True
    ).strip()


def get_main_status(repo_path):
    return subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=repo_path, text=True
    ).strip()


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

@pytest.fixture(scope="function")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    yield app
    QCoreApplication.processEvents()
    time.sleep(0.1)


@pytest.fixture
def remote_path(tmp_path):
    return create_seeded_remote(tmp_path)


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------

def test_machine_b_sees_machine_a_lock(qapp, remote_path, tmp_path):
    """Scenario A: B sees A's valid lock."""
    client_a = create_client(tmp_path, remote_path, "A")
    client_b = create_client(tmp_path, remote_path, "B")

    start_client(client_a)
    start_client(client_b)

    # Ensure B has an initial snapshot (poll once)
    spy_b_init = QSignalSpy(client_b["poller"].snapshot_changed)
    client_b["poller"].request_refresh()
    assert wait_for_signal(spy_b_init, timeout_ms=5000), "B initial snapshot failed"

    # A acquires lock
    result_a = client_a["cm"].request_write()
    assert result_a.is_granted, "A should acquire lock"

    # B refreshes and observes
    spy_b = QSignalSpy(client_b["poller"].snapshot_changed)
    client_b["poller"].request_refresh()
    assert wait_for_signal(spy_b, timeout_ms=5000), "B did not get snapshot after A lock"

    snapshot_b = client_b["poller"].get_last_snapshot()
    assert snapshot_b is not None, "B has no snapshot"
    assert snapshot_b.has_lock(), "B should see lock held"
    assert snapshot_b.lock_owner() == "User A", f"B sees owner {snapshot_b.lock_owner()}, expected User A"

    # Cleanup
    client_a["cm"].release_write()
    stop_client(client_a)
    stop_client(client_b)


def test_waiting_request_visible_cross_machine(qapp, remote_path, tmp_path):
    pytest.skip("WriteQueue is local runtime state; remote queue contract is a separate task.")


def test_machine_a_sees_waiting_request(qapp, remote_path, tmp_path):
    pytest.skip("WriteQueue is local runtime state; remote queue contract is a separate task.")


def test_release_becomes_visible_cross_machine(qapp, remote_path, tmp_path):
    """Scenario C: A releases, B observes free state."""
    client_a = create_client(tmp_path, remote_path, "A")
    client_b = create_client(tmp_path, remote_path, "B")
    try:
        start_client(client_a)
        start_client(client_b)
        assert client_a["cm"].request_write().is_granted
        assert wait_for_poll(client_b["poller"], 5000)
        assert client_b["poller"].get_last_snapshot().has_lock()

        assert client_a["cm"].release_write() is True
        assert wait_for_poll(client_b["poller"], 5000)
        assert not client_b["poller"].get_last_snapshot().has_lock()
    finally:
        try:
            client_a["cm"].release_write()
        except Exception:
            pass
        stop_client(client_a)
        stop_client(client_b)


def test_lease_renewal_remains_visible_cross_machine(qapp, remote_path, tmp_path):
    """Scenario D: A renews a valid lease; B continues to see A."""
    client_a = create_client(tmp_path, remote_path, "A", lease_duration_seconds=30)
    client_b = create_client(tmp_path, remote_path, "B")
    try:
        start_client(client_a)
        start_client(client_b)
        assert client_a["cm"].request_write().is_granted
        assert wait_for_poll(client_b["poller"], 5000)
        snap = client_b["poller"].get_last_snapshot()
        assert snap.has_lock() and snap.lock_owner() == "User A"

        session = client_a["cm"].get_session()
        assert session is not None
        assert client_a["provider"].renew_lock(
            session.username, session.session_id
        ), "Renewal should succeed while lease is valid"

        assert wait_for_poll(client_b["poller"], 5000)
        snap = client_b["poller"].get_last_snapshot()
        assert snap.has_lock() and snap.lock_owner() == "User A"

        remote_status = client_b["provider"].remote_lock_status()
        assert remote_status.get("locked") is True
        lease = remote_status.get("lease_expires_at")
        assert lease is not None
        assert datetime.fromisoformat(lease) > datetime.now()
    finally:
        try:
            client_a["cm"].release_write()
        except Exception:
            pass
        stop_client(client_a)
        stop_client(client_b)


def test_expired_lease_becomes_visible_cross_machine(qapp, remote_path, tmp_path):
    """Scenario E: A publishes an expired lease; B observes it."""
    client_a = create_client(
        tmp_path, remote_path, "A", lease_duration_seconds=30
    )
    client_b = create_client(tmp_path, remote_path, "B")

    try:
        # A is the state producer. Start it only long enough to acquire.
        start_client(client_a)
        assert client_a["cm"].request_write().is_granted

        # B is the observer.
        start_client(client_b)
        assert wait_for_poll(client_b["poller"], 5000)

        snap = client_b["poller"].get_last_snapshot()
        assert snap is not None
        assert snap.has_lock()
        assert snap.lock_owner() == "User A"

        # IMPORTANT: never mutate A's Git repository while Poller A can fetch.
        stop_client(client_a)

        provider_a = client_a["provider"]
        oid = provider_a._remote_lock_oid()
        assert oid is not None, "A lock OID must exist"

        # Materialize the remote object locally before modifying the payload.
        assert provider_a._fetch_lock_branch()
        lock_data = provider_a._read_lock_from_oid(oid)
        assert lock_data.get("locked") is True

        # Deterministic expiry: no sleep and no timing race.
        lock_data["lease_expires_at"] = (
            datetime.now() - timedelta(seconds=1)
        ).isoformat()

        commit_sha = provider_a._create_lock_commit_plumbing(
            lock_data, oid
        )
        assert commit_sha, "Failed to create expired lock commit"

        assert provider_a._push_lock_branch(
            commit_sha, oid
        ), "Failed to publish expired lock"

        # Only B polls after the remote mutation.
        assert wait_for_poll(client_b["poller"], 5000),             "B did not complete expired-lease poll"

        snapshot_b = client_b["poller"].get_last_snapshot()
        assert snapshot_b is not None

        remote_status = client_b["provider"].remote_lock_status()
        assert remote_status.get("locked") is True

        lease = remote_status.get("lease_expires_at")
        assert lease is not None
        assert datetime.fromisoformat(lease) <= datetime.now()

        # The poller is a state observer: `is_stale` means the POLL itself
        # failed, not that the remote lease is expired. Therefore an expired
        # remote lock may legitimately remain `locked=True` in the raw
        # snapshot. The visibility contract is that B observes the same
        # expired lease timestamp from the remote state.
        snapshot_lease = snapshot_b.remote_lock.get("lease_expires_at")
        assert snapshot_lease is not None,             "B snapshot did not expose lease_expires_at"
        assert datetime.fromisoformat(snapshot_lease) <= datetime.now(),             "B snapshot did not observe the expired lease"

        assert snapshot_b.poll_status == "success"
        assert snapshot_b.is_stale is False

    finally:
        stop_client(client_b)
        # A was already stopped before the direct Git mutation.
        try:
            client_a["cm"].release_write()
        except Exception:
            pass
        stop_client(client_a)

def test_main_isolation_cross_machine(qapp, remote_path, tmp_path):
    """Cross-machine collaboration operations never modify MAIN."""
    client_a = create_client(tmp_path, remote_path, "A")
    client_b = create_client(tmp_path, remote_path, "B")
    head_a_before = get_main_head(client_a["repo_path"])
    status_a_before = get_main_status(client_a["repo_path"])
    head_b_before = get_main_head(client_b["repo_path"])
    status_b_before = get_main_status(client_b["repo_path"])
    try:
        start_client(client_a)
        start_client(client_b)
        assert client_a["cm"].request_write().is_granted
        client_b["cm"].request_write()
        client_a["cm"].release_write()
        client_b["cm"].cancel_waiting_request()
        assert wait_for_poll(client_a["poller"], 5000)
        assert wait_for_poll(client_b["poller"], 5000)
    finally:
        try:
            client_a["cm"].release_write()
        except Exception:
            pass
        stop_client(client_a)
        stop_client(client_b)

    assert get_main_head(client_a["repo_path"]) == head_a_before
    assert get_main_status(client_a["repo_path"]) == status_a_before
    assert get_main_head(client_b["repo_path"]) == head_b_before
    assert get_main_status(client_b["repo_path"]) == status_b_before

