"""Regression tests for queued-writer runtime snapshot consistency."""

from datetime import datetime, timedelta

from centermanager.platform.collaboration import CollaborationManager


class FakeRemoteProvider:
    def __init__(self):
        self.lock = {"locked": False, "session_id": None, "lease_expires_at": None}
        self.acquired = False
        self.released = False

    def remote_lock_status(self):
        return dict(self.lock)

    def acquire_lock(self, lock_data):
        self.acquired = True
        self.lock = dict(lock_data)
        return True

    def release_lock(self, username):
        self.released = True
        self.lock = {"locked": False, "session_id": None}
        return True


def test_remote_waiting_grant_runs_handoff_guard_before_consuming_queue(tmp_path):
    provider = FakeRemoteProvider()
    cm = CollaborationManager(runtime_root=tmp_path, sync_provider=provider)
    cm.initialize("u1", "User 1", "admin")

    # Force a waiting request owned by this session.
    result = cm._enqueue_or_return_waiting("test", "req-1")
    assert result.is_waiting
    assert cm._queue.get_by_session(cm.get_session_id()) is not None

    order = []
    cm.set_write_handoff_guard(lambda: order.append("sync") or True)

    assert cm.grant_existing_waiting_request("req-1") is True
    assert order == ["sync"]
    assert provider.acquired is True
    assert cm._queue.get_by_session(cm.get_session_id()) is None
    assert cm.is_writing() is True


def test_remote_waiting_grant_keeps_queue_when_handoff_sync_fails(tmp_path):
    provider = FakeRemoteProvider()
    cm = CollaborationManager(runtime_root=tmp_path, sync_provider=provider)
    cm.initialize("u1", "User 1", "admin")
    result = cm._enqueue_or_return_waiting("test", "req-1")
    assert result.is_waiting

    cm.set_write_handoff_guard(lambda: False)

    assert cm.grant_existing_waiting_request("req-1") is False
    # The handoff guard runs before remote acquisition, so a failed
    # pre-grant sync must not acquire or release a remote lock.
    assert provider.released is True
    assert cm.is_writing() is False
    assert cm._queue.get_by_session(cm.get_session_id()) is not None
