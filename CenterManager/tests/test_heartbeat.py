import pytest
from pathlib import Path
from datetime import datetime, timedelta
import time

from centermanager.platform.collaboration.heartbeat import HeartbeatRepository, HeartbeatManager
from centermanager.platform.collaboration.json_lock_repository import JsonLockRepository
from centermanager.platform.collaboration.runtime_session import RuntimeSession

# Thay vì sử dụng HeartbeatService, dùng HeartbeatRepository + HeartbeatManager

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
    # Đợi một chút để heartbeat chạy
    time.sleep(1.5)
    manager.update()  # force update
    
    # Kiểm tra file heartbeat đã được tạo
    hb_file = heartbeat_repo._heartbeat_dir / f"{session.session_id}.json"
    assert hb_file.exists()
    
    manager.stop()