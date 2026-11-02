"""QA-S02: multi-client WRITE queue lifecycle in disposable bare Git.

Independent runtimes, no production remote/token/data. These are process-level
simulations, not Windows packaged two-PC staging acceptance.
"""
from tests.test_cross_machine_shared_write_queue import (
    _seed_remote, _make_machine,
)


def test_cancelled_waiter_vanishes_for_all_clients_without_releasing_owner(tmp_path):
    remote = _seed_remote(tmp_path)
    owner, owner_provider = _make_machine(tmp_path, remote, "owner")
    waiter, waiter_provider = _make_machine(tmp_path, remote, "waiter")
    observer, observer_provider = _make_machine(tmp_path, remote, "observer")
    try:
        assert owner.request_write().is_granted
        owner_session = owner.get_session_id()
        owner_oid = owner_provider._remote_lock_oid()
        queued = waiter.request_write()
        assert queued.is_waiting
        assert owner.get_queue()["length"] == 1
        assert waiter.cancel_waiting_request()
        assert waiter.cancel_waiting_request()  # Cancellation is idempotent.
        for manager in (owner, waiter, observer):
            assert manager.get_queue()["length"] == 0
        assert owner_provider._remote_lock_oid() == owner_oid
        assert observer_provider.remote_lock_status()["session_id"] == owner_session
        assert owner.is_writing()
    finally:
        waiter.cancel_waiting_request()
        observer.cancel_waiting_request()
        if owner.is_writing():
            owner.release_write()
        for client in (observer, waiter, owner):
            client.shutdown()


def test_waiter_cancellation_does_not_remove_other_waiters(tmp_path):
    remote = _seed_remote(tmp_path)
    owner, _ = _make_machine(tmp_path, remote, "owner2")
    first, _ = _make_machine(tmp_path, remote, "first")
    second, _ = _make_machine(tmp_path, remote, "second")
    try:
        assert owner.request_write().is_granted
        first_req = first.request_write()
        second_req = second.request_write()
        assert first_req.is_waiting and second_req.is_waiting
        assert owner.get_queue()["length"] == 2
        assert first.cancel_waiting_request()
        for client in (owner, first, second):
            queue = client.get_queue()
            assert queue["length"] == 1
            assert queue["next"]["request_id"] == second_req.request_id
        assert owner.is_writing()
    finally:
        first.cancel_waiting_request()
        second.cancel_waiting_request()
        if owner.is_writing():
            owner.release_write()
        for client in (second, first, owner):
            client.shutdown()
