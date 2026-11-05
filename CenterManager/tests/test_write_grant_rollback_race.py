"""Regression: background queue refresh cannot delete an in-flight granted lock."""
import threading
from types import SimpleNamespace

from centermanager.platform.collaboration.collaboration_manager import CollaborationManager
from centermanager.services.write_transaction import WriteTransactionManager


def _manager_with_pending_lock():
    manager = CollaborationManager.__new__(CollaborationManager)
    manager._state_mutex = threading.RLock()
    manager._ungranted_lock = True
    manager._cancel_pending = False
    manager._session = SimpleNamespace(session_id="one-session")
    manager._pending_request = None
    manager._ensure_initialized = lambda: None
    manager._queue_get_by_session = lambda session_id: None
    manager._get_remote_lock_status = lambda: {
        "state": "ACTIVE", "session_id": "one-session"
    }
    calls = []
    manager._release_remote_session = lambda: calls.append("remote-release") or True
    manager._lock = SimpleNamespace(
        _force_release=lambda: calls.append("local-release")
    )
    return manager, calls


def test_poller_refresh_cannot_rollback_provisional_grant_while_mutex_held():
    manager, calls = _manager_with_pending_lock()
    entered = threading.Event()
    finished = threading.Event()

    def background_refresh():
        entered.set()
        manager.refresh_waiting_request()
        finished.set()

    with manager._state_mutex:
        worker = threading.Thread(target=background_refresh, daemon=True)
        worker.start()
        assert entered.wait(timeout=2)
        assert not finished.wait(timeout=0.05)
        # Grant commits while holding the same state mutex.
        manager._ungranted_lock = False
    worker.join(timeout=2)
    assert finished.is_set()
    assert calls == []


def test_uncommitted_lock_still_rolls_back_when_no_grant_active():
    manager, calls = _manager_with_pending_lock()
    assert manager._rollback_ungranted_lock() is True
    assert calls == ["remote-release", "local-release"]
    assert manager._ungranted_lock is False


class Provider:
    def __init__(self, *, remote_oid="owned", owned_oid="owned"):
        self.remote_oid = remote_oid
        self.owned_oid = owned_oid

    def remote_lock_status(self):
        return {
            "state": "ACTIVE", "locked": True, "session_id": "one-session",
            "owner": "user", "oid": self.remote_oid,
            "lease_revision": 1,
        }

    def owns_lock_observation(self, remote, owner, session_id):
        return (
            remote["oid"] == self.owned_oid
            and remote["owner"] == owner
            and remote["session_id"] == session_id
        )


def _write_transaction(provider, *, authority=True):
    session = SimpleNamespace(username="user", session_id="one-session")
    collab = SimpleNamespace(
        _sync_provider=provider, get_session=lambda: session,
        validate_write_authority=lambda obj: {
            "valid": authority, "generation": 4,
            "generation_authoritative": True,
            "reason": "Remote lock not held" if not authority else "",
        },
        is_writing=lambda: True,
    )
    txn = WriteTransactionManager(collab)
    txn._expected_generation = 4
    return txn


def test_final_grant_rejects_same_session_with_different_lock_oid():
    txn = _write_transaction(Provider(remote_oid="replaced"))
    assert txn._verify_grant_before_editing() is False
    assert "Remote WRITE ownership" in txn.last_start_error


def test_final_grant_accepts_exact_owned_lock_oid():
    txn = _write_transaction(Provider())
    assert txn._verify_grant_before_editing() is True


def test_final_grant_rejects_missing_remote_authority():
    txn = _write_transaction(Provider(), authority=False)
    assert txn._verify_grant_before_editing() is False
