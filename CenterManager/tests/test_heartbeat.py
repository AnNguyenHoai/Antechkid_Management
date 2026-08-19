# -*- coding: utf-8 -*-
"""
Tests for Heartbeat functionality.
"""

import pytest
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.platform.collaboration.heartbeat import HeartbeatRepository, HeartbeatManager
from centermanager.platform.collaboration.runtime_session import RuntimeSession
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.events.event_bus import EventBus
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider


@pytest.fixture
def lock_repo(tmp_path):
    lock_file = tmp_path / "lock.json"
    return JsonLockRepository(lock_file)


def _create_locked_lock(lock_repo, owner="test_owner", session_id="sess_123"):
    lock_repo.save_lock({
        "locked": True,
        "owner": owner,
        "session_id": session_id,
        "started_at": datetime.now().isoformat(),
        "last_heartbeat": datetime.now().isoformat(),
        "heartbeat_version": 0,
    })


def test_heartbeat_start_stop(lock_repo):
    _create_locked_lock(lock_repo)
    session = RuntimeSession(user_id="test", username="testuser")
    heartbeat_repo = HeartbeatRepository(lock_repo._lock_file.parent / "heartbeat")
    manager = HeartbeatManager(repo=heartbeat_repo, session=session, interval_seconds=1)

    assert not manager._running
    manager.start()
    assert manager._running
    manager.stop()
    assert not manager._running


def test_heartbeat_update(lock_repo):
    _create_locked_lock(lock_repo)
    session = RuntimeSession(user_id="test", username="testuser")
    heartbeat_repo = HeartbeatRepository(lock_repo._lock_file.parent / "heartbeat")
    manager = HeartbeatManager(repo=heartbeat_repo, session=session, interval_seconds=1)

    manager.start()
    time.sleep(1.5)
    manager.update()  # force update

    # Kiểm tra file heartbeat đã được tạo
    hb_file = heartbeat_repo._heartbeat_dir / f"{session.session_id}.json"
    assert hb_file.exists()

    manager.stop()

def test_heartbeat_repository_does_not_dirty_git(fresh_center_manager_remote, tmp_path):
    """
    Focused test: Heartbeat updates must NOT dirty the Git working tree.
    Does NOT use lock acquisition or CollaborationManager.
    Only HeartbeatRepository and real Git status check.
    """
    import subprocess
    from pathlib import Path
    import time

    from centermanager.platform.collaboration.heartbeat import HeartbeatRepository
    from centermanager.platform.collaboration.runtime_session import RuntimeSession

    # 1. Clone the seeded bare remote into a local repository
    repo_path = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(fresh_center_manager_remote), str(repo_path)],
        check=True
    )

    # 2. Ensure clean Git status before test
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", "Initial Git status must be clean"

    # 3. Create heartbeat directory OUTSIDE the Git repository
    runtime_root = tmp_path / "runtime"
    heartbeat_dir = runtime_root / "collaboration" / "heartbeat"
    heartbeat_dir.mkdir(parents=True, exist_ok=True)

    # 4. Create HeartbeatRepository
    repo = HeartbeatRepository(heartbeat_dir)

    # 5. Create a session and update heartbeat
    session = RuntimeSession(user_id="test_user", username="test_user", role="admin")
    repo.update(session)
    time.sleep(0.1)  # small delay to ensure timestamp changes

    # 6. Update heartbeat again
    repo.update(session)

    # 7. Verify heartbeat file exists
    heartbeat_file = heartbeat_dir / f"{session.session_id}.json"
    assert heartbeat_file.exists(), "Heartbeat file should exist"

    # 8. Check Git status - must remain clean
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", f"Git working tree is dirty: {result.stdout}"

    # 9. Cleanup
    repo.remove(session.session_id)
    assert not heartbeat_file.exists(), "Heartbeat file should be removed"
    
def test_heartbeat_does_not_dirty_git(fresh_center_manager_remote, tmp_path):
    """
    Regression test: heartbeat updates must NOT dirty the Git working tree.
    Uses a real GitSynchronizationProvider and CollaborationManager.
    """
    # 1. Clone the seeded bare remote into a local repository
    repo_path = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "--branch", "main", str(fresh_center_manager_remote), str(repo_path)],
        check=True
    )

    # 2. Create GitSynchronizationProvider for the local repo
    provider = GitSynchronizationProvider(
        repo_path=repo_path,
        repository_url=str(fresh_center_manager_remote),
        token="",
        branch="main"
    )
    provider.connect()

    # 3. Create CollaborationManager with sync_provider
    runtime_root = tmp_path / "runtime"
    event_bus = EventBus()
    cm = CollaborationManager(
        runtime_root=runtime_root,
        event_bus=event_bus,
        sync_provider=provider
    )

    # 4. Verify heartbeat directory is OUTSIDE the Git repository
    assert cm._heartbeat_dir.parent != repo_path
    assert cm._heartbeat_dir.parent == runtime_root / "collaboration"

    # 5. Initialize and acquire lock (this starts heartbeat)
    cm.initialize("test_user", "test_user", "admin")
    cm.request_write()

    # 6. Let heartbeat run and update a few times
    time.sleep(1)
    cm.heartbeat()
    time.sleep(1)

    # 7. Check Git status - must be clean
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    assert result.stdout.strip() == "", f"Git working tree is dirty: {result.stdout}"

    # 8. Check that heartbeat file exists outside repo
    heartbeat_file = cm._heartbeat_dir / f"{cm._session.session_id}.json"
    assert heartbeat_file.exists()

    # 9. Cleanup
    cm.release_write()
    cm.shutdown()