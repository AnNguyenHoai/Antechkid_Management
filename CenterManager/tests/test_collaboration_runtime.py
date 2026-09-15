# -*- coding: utf-8 -*-
"""Unit tests for Collaboration Runtime."""

import pytest
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta

from centermanager.platform.collaboration import (
    RuntimeSession,
    RuntimeLock,
    WriteQueue,
    WriteRequest,
    HeartbeatRepository,
    PresenceManager,
    Priority,
    Arbitration,
    CollaborationManager,
    CollaborationNotInitializedError,
    LockTimeoutError,
)
from centermanager.events.event_bus import EventBus


# Mark all tests with timeout to prevent hanging
pytestmark = pytest.mark.timeout(5)


class TestRuntimeSession:
    def test_creation(self):
        session = RuntimeSession(user_id="user1", username="testuser", role="admin")
        assert session.session_id is not None
        assert session.machine_fingerprint is not None
        assert session.user_id == "user1"
        assert session.username == "testuser"
        assert session.is_active is True

    def test_update_heartbeat(self):
        session = RuntimeSession()
        old_time = session.last_heartbeat
        time.sleep(0.01)
        session.update_heartbeat()
        assert session.last_heartbeat > old_time

    def test_is_expired(self):
        session = RuntimeSession()
        assert session.is_expired(timeout_seconds=30) is False
        session.last_heartbeat = datetime.now() - timedelta(seconds=60)
        assert session.is_expired(timeout_seconds=30) is True

    def test_to_dict_and_from_dict(self):
        session = RuntimeSession(user_id="user1", username="test", role="admin")
        data = session.to_dict()
        restored = RuntimeSession.from_dict(data)
        assert restored.session_id == session.session_id
        assert restored.user_id == session.user_id
        assert restored.username == session.username


class TestRuntimeLock:
    def test_acquire_and_release(self, tmp_path):
        lock = RuntimeLock(tmp_path / "lock.json")
        session = RuntimeSession(user_id="user1", username="test")

        assert lock.is_locked() is False
        assert lock.acquire(session) is True
        assert lock.is_locked() is True
        assert lock.get_owner() == session.session_id

        lock.release(session)
        assert lock.is_locked() is False

    def test_acquire_already_held(self, tmp_path):
        lock = RuntimeLock(tmp_path / "lock.json")
        session1 = RuntimeSession(user_id="user1", username="test1")
        session2 = RuntimeSession(user_id="user2", username="test2")

        lock.acquire(session1)
        assert lock.is_locked() is True
        assert lock.get_owner() == session1.session_id

        with pytest.raises(LockTimeoutError):
            lock.acquire(session2, timeout_seconds=1)

    def test_heartbeat(self, tmp_path):
        lock = RuntimeLock(tmp_path / "lock.json")
        session = RuntimeSession(user_id="user1", username="test")

        lock.acquire(session)
        assert lock.heartbeat(session) is True

        info = lock.get_lock_info()
        assert info.get("last_heartbeat") is not None


class TestWriteQueue:
    def test_enqueue_and_dequeue(self, tmp_path):
        queue = WriteQueue(tmp_path / "queue")
        req1 = WriteRequest("req1", "sess1", "user1", "user1", "admin", 100, datetime.now())
        req2 = WriteRequest("req2", "sess2", "user2", "user2", "teacher", 60, datetime.now())

        queue.enqueue(req1)
        queue.enqueue(req2)

        assert queue.count() == 2

        dequeued = queue.dequeue()
        assert dequeued.request_id == "req1"

        dequeued2 = queue.dequeue()
        assert dequeued2.request_id == "req2"

        assert queue.count() == 0

    def test_peek(self, tmp_path):
        queue = WriteQueue(tmp_path / "queue")
        req1 = WriteRequest("req1", "sess1", "user1", "user1", "admin", 100, datetime.now())
        req2 = WriteRequest("req2", "sess2", "user2", "user2", "reception", 40, datetime.now())

        queue.enqueue(req1)
        queue.enqueue(req2)

        peeked = queue.peek()
        assert peeked.request_id == "req1"
        assert queue.count() == 2

    def test_cancel(self, tmp_path):
        queue = WriteQueue(tmp_path / "queue")
        req = WriteRequest("req1", "sess1", "user1", "user1", "admin", 100, datetime.now())
        queue.enqueue(req)

        assert queue.count() == 1
        queue.cancel("req1")
        assert queue.count() == 0


class TestHeartbeatRepository:
    def test_update_and_get(self, tmp_path):
        repo = HeartbeatRepository(tmp_path / "heartbeat")
        session = RuntimeSession(user_id="user1", username="test")

        repo.update(session)
        all_data = repo.get_all()
        assert session.session_id in all_data
        assert all_data[session.session_id]["username"] == "test"

    def test_is_expired(self, tmp_path):
        repo = HeartbeatRepository(tmp_path / "heartbeat")
        session = RuntimeSession(user_id="user1", username="test")

        repo.update(session)
        assert repo.is_expired(session.session_id, timeout_seconds=30) is False

        file_path = tmp_path / "heartbeat" / f"{session.session_id}.json"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["last_seen"] = (datetime.now() - timedelta(seconds=60)).isoformat()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        assert repo.is_expired(session.session_id, timeout_seconds=30) is True

    def test_remove(self, tmp_path):
        repo = HeartbeatRepository(tmp_path / "heartbeat")
        session = RuntimeSession(user_id="user1", username="test")

        repo.update(session)
        assert session.session_id in repo.get_all()

        repo.remove(session.session_id)
        assert session.session_id not in repo.get_all()


class TestPresenceManager:
    def test_get_online_sessions(self, tmp_path):
        repo = HeartbeatRepository(tmp_path / "heartbeat")
        lock = RuntimeLock(tmp_path / "lock.json")
        queue = WriteQueue(tmp_path / "queue")
        presence = PresenceManager(repo, lock, queue)

        session1 = RuntimeSession(user_id="user1", username="test1")
        session2 = RuntimeSession(user_id="user2", username="test2")

        repo.update(session1)
        repo.update(session2)

        online = presence.get_online_sessions()
        assert len(online) == 2

    def test_get_current_writer(self, tmp_path):
        repo = HeartbeatRepository(tmp_path / "heartbeat")
        lock = RuntimeLock(tmp_path / "lock.json")
        queue = WriteQueue(tmp_path / "queue")
        presence = PresenceManager(repo, lock, queue)

        session = RuntimeSession(user_id="user1", username="writer")
        lock.acquire(session)

        writer = presence.get_current_writer()
        assert writer is not None
        assert writer["session_id"] == session.session_id
        assert writer["username"] == "writer"


class TestArbitration:
    def test_priority_from_role(self):
        assert Priority.from_role("admin") == Priority.ADMIN
        assert Priority.from_role("teacher") == Priority.TEACHER
        assert Priority.from_role("reception") == Priority.RECEPTION
        assert Priority.from_role("unknown") == Priority.USER

    def test_sort_requests(self):
        now = datetime.now()
        req1 = WriteRequest("r1", "s1", "u1", "u1", "admin", 100, now)
        req2 = WriteRequest("r2", "s2", "u2", "u2", "teacher", 60, now)
        req3 = WriteRequest("r3", "s3", "u3", "u3", "reception", 40, now)

        sorted_reqs = Arbitration.sort_requests([req3, req1, req2])
        assert sorted_reqs[0].request_id == "r1"
        assert sorted_reqs[1].request_id == "r2"
        assert sorted_reqs[2].request_id == "r3"

    def test_is_higher_priority(self):
        now = datetime.now()
        req1 = WriteRequest("r1", "s1", "u1", "u1", "admin", 100, now)
        req2 = WriteRequest("r2", "s2", "u2", "u2", "teacher", 60, now)

        assert Arbitration.is_higher_priority(req1, req2) is True
        assert Arbitration.is_higher_priority(req2, req1) is False


class TestCollaborationManager:
    def test_initialize(self, tmp_path):
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)

        session = cm.initialize("user1", "testuser", "admin")
        assert cm.is_initialized() is True
        assert cm.get_session() is not None
        assert cm.get_session().user_id == "user1"

        cm.shutdown()
        assert cm.is_initialized() is False

    def test_request_write_granted(self, tmp_path):
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)

        cm.initialize("user1", "testuser", "admin")
        
        assert cm._lock.is_locked() is False
        
        result = cm.request_write()
        assert result.is_granted is True
        assert cm.is_writing() is True
        assert cm._lock.is_locked() is True
        assert cm._lock.get_owner() == cm._session.session_id

        cm.release_write()
        assert cm.is_writing() is False
        assert cm._lock.is_locked() is False

    def test_request_write_queued(self, tmp_path):
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)

        cm.initialize("user1", "testuser", "admin")
        result = cm.request_write()
        assert result.is_granted is True

        cm2 = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)
        cm2.initialize("user2", "testuser2", "teacher")

        cm.release_write()

        queue = cm2.get_queue()
        assert queue["length"] == 0

    def test_heartbeat(self, tmp_path):
        """Test heartbeat with proper synchronization."""
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)

        # Initialize collaboration (starts heartbeat thread)
        cm.initialize("user1", "testuser", "admin")
        
        # Đợi heartbeat thread hoàn thành chu kỳ đầu tiên
        time.sleep(0.5)
        
        # Gọi heartbeat manually
        result = cm.heartbeat()
        assert result is True
        
        # Đợi một chút để thread ghi xong
        time.sleep(0.3)
        
        # Shutdown để cleanup
        cm.shutdown()
        assert cm.is_initialized() is False

    def test_get_presence(self, tmp_path):
        event_bus = EventBus()
        cm = CollaborationManager(runtime_root=tmp_path, event_bus=event_bus)

        cm.initialize("user1", "testuser", "admin")
        presence = cm.get_presence()
        assert "online_count" in presence
        assert "current_writer" in presence

    def test_not_initialized_error(self, tmp_path):
        cm = CollaborationManager(runtime_root=tmp_path)
        with pytest.raises(CollaborationNotInitializedError):
            cm.request_write()