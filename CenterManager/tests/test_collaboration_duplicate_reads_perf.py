"""Regression tests for reusing remote observations within one decision.

These tests intentionally stop before any remote CAS mutation.
"""
from types import SimpleNamespace

from centermanager.platform.collaboration.collaboration_manager import CollaborationManager


def test_pre_acquire_queue_checks_share_one_snapshot():
    manager = CollaborationManager.__new__(CollaborationManager)
    manager._cancel_pending = False
    manager._rollback_ungranted_lock = lambda: True
    manager._session = SimpleNamespace(session_id="session-a")
    manager._waiting_handoff_code = ""
    calls = []

    def queue_requests():
        calls.append("read")
        return [SimpleNamespace(session_id="session-a", request_id="other-request")]

    manager._queue_requests = queue_requests
    manager._get_remote_lock_status = lambda: (_ for _ in ()).throw(
        AssertionError("mismatched queue must not proceed to lock acquisition")
    )

    assert manager._grant_remote_request("wanted-request", run_handoff=False) is False
    assert manager._waiting_handoff_code == "QUEUE_HEAD_MISMATCH"
    assert calls == ["read"]


def test_sync_local_lock_reuses_supplied_remote_observation():
    manager = CollaborationManager.__new__(CollaborationManager)
    manager._sync_provider = object()
    manager._session = SimpleNamespace(session_id="session-a")
    manager._is_lease_valid = lambda deadline: deadline == "valid"
    calls = []
    manager._get_remote_lock_status = lambda: (_ for _ in ()).throw(
        AssertionError("supplied observation must not be fetched again")
    )
    manager._lock = SimpleNamespace(
        _write_lock=lambda data: calls.append(data),
        _force_release=lambda: (_ for _ in ()).throw(
            AssertionError("valid owner must not be released")
        ),
    )
    remote = {
        "state": "ACTIVE", "locked": True, "session_id": "session-a",
        "owner": "user", "username": "user", "lease_expires_at": "valid",
        "lock_generation": 9, "lease_revision": 4,
    }

    manager._sync_local_lock(remote)

    assert len(calls) == 1
    assert calls[0]["session_id"] == "session-a"
    assert calls[0]["lock_generation"] == 9
    assert manager._lock_acquired is True
    assert manager._is_writing is True
