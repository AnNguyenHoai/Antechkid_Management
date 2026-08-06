# -*- coding: utf-8 -*-
import pytest
from pathlib import Path
from datetime import datetime, timedelta
import time

from centermanager.platform.collaboration.heartbeat import HeartbeatService
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.platform.collaboration.lock_manager import LockManager


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
        "heartbeat_version": 0,  # start at 0
    })


def test_heartbeat_start_stop(lock_repo):
    _create_locked_lock(lock_repo)
    service = HeartbeatService(lock_repo, interval_seconds=1)
    assert not service.is_running

    service.start("test_owner", "sess_123")
    assert service.is_running
    status = service.get_status()
    assert status.owner == "test_owner"
    assert status.session_id == "sess_123"

    service.stop()
    assert not service.is_running


def test_heartbeat_update(lock_repo):
    _create_locked_lock(lock_repo)
    service = HeartbeatService(lock_repo, interval_seconds=1)
    service.start("test_owner", "sess_123")

    # start() already does an initial update (0→1)
    # First explicit update should increment from 1 to 2
    service.update()
    lock = lock_repo.get_lock()
    assert lock.get("locked") is True
    assert lock.get("owner") == "test_owner"
    assert "last_heartbeat" in lock
    assert lock.get("heartbeat_version") == 2

    # Second explicit update should increment to 3
    service.update()
    lock = lock_repo.get_lock()
    assert lock.get("heartbeat_version") == 3

    service.stop()


def test_heartbeat_stale_detection(lock_repo):
    _create_locked_lock(lock_repo)
    service = HeartbeatService(lock_repo, interval_seconds=1)
    service.start("test_owner", "sess_123")
    service.update()  # ensure heartbeat is written

    lock_manager = LockManager(lock_repo, timeout_seconds=2)
    assert not lock_manager.is_stale()

    # Manually set last_heartbeat to an old timestamp
    lock = lock_repo.get_lock()
    old_time = (datetime.now() - timedelta(seconds=3)).isoformat()
    lock["last_heartbeat"] = old_time
    lock_repo.save_lock(lock)

    # Now it should be stale
    assert lock_manager.is_stale()

    service.stop()