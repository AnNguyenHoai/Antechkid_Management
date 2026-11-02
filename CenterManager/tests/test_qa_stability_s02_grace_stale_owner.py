"""QA-S02 R2 — grace expiry, stale-owner release, queue continuity.

Synthetic clocks, disposable local bare Git, no real accounts or production DB.
This tests authority and queue transitions, not a packaged two-PC Windows UAT.
"""
import pytest

from tests.test_e0_write_recovery_audit import machines, clock, handoff  # noqa: F401
from centermanager.services.write_transaction import (
    WriteTransactionManager, WriteTransactionState,
)


def test_expired_owner_remains_protected_during_grace_then_waiter_granted(machines, clock):
    owner, old_provider = machines("qa-grace-old", username="shared-user")
    waiter, new_provider = machines("qa-grace-new", username="shared-user")
    assert owner.request_write().is_granted
    old_session = owner.get_session_id()
    old_oid = old_provider._remote_lock_oid()
    clock.at(61)
    tx = WriteTransactionManager(waiter)
    assert not tx.start_editing()
    assert tx.state == WriteTransactionState.WAITING
    assert waiter.has_pending_waiting_request()
    assert not waiter.is_writing()
    assert old_provider.remote_lock_status()["session_id"] == old_session

    # Keep the same pending request alive rather than silently dropping it.
    for second in range(81, 660, 20):
        clock.at(second)
        assert waiter.refresh_waiting_request()
        assert waiter.has_pending_waiting_request()
    clock.at(660)
    handoff(waiter)
    assert waiter.is_writing()
    assert new_provider.remote_lock_status()["session_id"] == waiter.get_session_id()
    assert waiter.get_session_id() != old_session

    new_oid = new_provider._remote_lock_oid()
    assert new_oid != old_oid
    assert not old_provider.release_lock(
        "shared-user", session_id=old_session, expected_oid=old_oid,
    )
    assert new_provider._remote_lock_oid() == new_oid
    assert waiter.is_writing()


def test_cancel_grace_waiting_removes_remote_request_without_releasing_owner(machines, clock):
    owner, owner_provider = machines("qa-grace-cancel-owner")
    waiter, _ = machines("qa-grace-cancel-waiter")
    assert owner.request_write().is_granted
    original_oid = owner_provider._remote_lock_oid()
    original_session = owner.get_session_id()
    clock.at(61)
    tx = WriteTransactionManager(waiter)
    assert not tx.start_editing()
    assert tx.state == WriteTransactionState.WAITING
    assert waiter.has_pending_waiting_request()
    assert waiter.cancel_waiting_request()  # Verified remote queue removal.
    tx.cancel_waiting()  # Then reconcile local UI transaction projection.
    assert tx.state == WriteTransactionState.IDLE
    assert not waiter.has_pending_waiting_request()
    assert owner.get_queue()["length"] == 0
    assert owner_provider._remote_lock_oid() == original_oid
    assert owner_provider.remote_lock_status()["session_id"] == original_session
