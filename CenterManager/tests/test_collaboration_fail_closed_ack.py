# -*- coding: utf-8 -*-
"""Regression tests for fail-closed collaboration acknowledgement semantics."""
from datetime import datetime, timedelta
from pathlib import Path

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager, WriteRequestResult
from centermanager.platform.collaboration.write_queue import WriteRequest
from centermanager.services.write_transaction import (
    WriteTransactionManager,
    WriteTransactionState,
)


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager"


class FakeRemoteProvider:
    def __init__(self):
        self.queue = []
        self.lock = {"locked": False, "owner": None, "session_id": None}
        self.enqueue_ok = True
        self.cancel_ok = True
        self.release_ok = True
        self.release_calls = 0

    def remote_queue_status(self):
        requests = list(self.queue)
        return {
            "length": len(requests),
            "requests": requests,
            "next": requests[0] if requests else None,
        }

    def enqueue_remote_write_request(self, request):
        if not self.enqueue_ok:
            return False
        self.queue.append(dict(request))
        return True

    def refresh_remote_write_request(self, request_id, session_id):
        return True

    def cancel_remote_write_request(self, request_id, session_id=None):
        if not self.cancel_ok:
            return False
        before = len(self.queue)
        self.queue = [
            item
            for item in self.queue
            if not (
                item.get("request_id") == request_id
                and (session_id is None or item.get("session_id") == session_id)
            )
        ]
        return True  # idempotent, acknowledged cancellation barrier

    def remote_lock_status(self):
        return dict(self.lock)

    def acquire_lock(self, lock_data):
        self.lock = dict(lock_data)
        self.lock["locked"] = True
        self.lock["lease_expires_at"] = (
            datetime.now() + timedelta(seconds=60)
        ).isoformat()
        return True

    def release_lock(self, owner, session_id=None):
        self.release_calls += 1
        if not self.release_ok:
            return False
        self.lock = {"locked": False, "owner": None, "session_id": None}
        return True


def _manager(tmp_path, provider):
    cm = CollaborationManager(
        runtime_root=tmp_path,
        event_bus=EventBus(),
        sync_provider=provider,
    )
    cm.initialize("user_b", "User B", "admin")
    return cm


def test_remote_enqueue_failure_never_reports_waiting(tmp_path):
    provider = FakeRemoteProvider()
    provider.lock = {
        "locked": True,
        "owner": "User A",
        "session_id": "session-a",
        "lease_expires_at": (
            datetime.now() + timedelta(seconds=60)
        ).isoformat(),
    }
    provider.enqueue_ok = False
    cm = _manager(tmp_path, provider)
    try:
        result = cm.request_write()
        assert result.result == WriteRequestResult.ERROR
        assert not result.is_waiting
        assert result.position == 0
        assert provider.queue == []
    finally:
        cm.shutdown()


def test_grant_rolls_back_when_queue_request_cannot_be_consumed(tmp_path):
    provider = FakeRemoteProvider()
    cm = _manager(tmp_path, provider)
    try:
        request = WriteRequest(
            request_id="req-b",
            session_id=cm.get_session_id(),
            user_id="user_b",
            username="User B",
            role="admin",
            priority=100,
            timestamp=datetime.now(),
        )
        provider.queue = [request.to_dict()]
        provider.cancel_ok = False

        granted = cm.grant_existing_waiting_request("req-b")

        assert granted is False
        assert provider.release_calls == 1
        assert cm.is_writing() is False
        assert provider.queue[0]["request_id"] == "req-b"
    finally:
        cm.shutdown()


def test_failed_remote_release_retains_local_write_projection(tmp_path):
    provider = FakeRemoteProvider()
    cm = _manager(tmp_path, provider)
    try:
        cm._is_writing = True
        cm._lock_acquired = True
        provider.release_ok = False

        assert cm.release_write() is False
        assert cm.is_writing() is True
        assert cm._lock_acquired is True
    finally:
        provider.release_ok = True
        cm.shutdown()


class _LockStub:
    def clear_finishing_data(self):
        return None


class _PublishedCollabStub:
    def __init__(self):
        self._lock = _LockStub()
        self._sync_provider = object()
        self.release_ok = False
        self.writing = True

    def is_writing(self):
        return self.writing

    def release_write(self):
        if not self.release_ok:
            return False
        self.writing = False
        return True

    def get_session(self):
        return None

    def resume_write_lease_renewal(self):
        return None


class _PublishServiceStub:
    def publish_only(self, **kwargs):
        return True


def test_successful_publish_does_not_claim_completion_until_release_confirmed():
    collab = _PublishedCollabStub()
    tx = WriteTransactionManager(collab)
    tx.set_sync_service(_PublishServiceStub())
    tx._state = WriteTransactionState.LOCAL_SAVED

    assert tx._publish() is True
    assert tx.state == WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING
    assert collab.writing is True

    collab.release_ok = True
    assert tx.retry_lock_release() is True
    assert tx.state == WriteTransactionState.IDLE
    assert collab.writing is False


def test_error_snapshot_cannot_cancel_authoritative_waiting_contract():
    source = (SRC / "ui" / "main_window.py").read_text(encoding="utf-8")
    start = source.index("def _reconcile_waiting_transaction")
    end = source.index("def _project_holder_waiting_requests", start)
    body = source[start:end]

    assert 'snapshot.poll_status != "success"' in body
    assert "snapshot.is_stale" in body
    assert "self._transaction.cancel_waiting(" in body


def test_remote_queue_read_failure_is_not_converted_to_empty_queue_contract():
    source = (
        SRC
        / "platform"
        / "synchronization"
        / "git_synchronization_provider.py"
    ).read_text(encoding="utf-8")
    start = source.index("def remote_queue_status")
    end = source.index("def enqueue_remote_write_request", start)
    body = source[start:end]

    assert 'return {"length": 0, "requests": [], "next": None}' not in body
    assert "except Exception" not in body
