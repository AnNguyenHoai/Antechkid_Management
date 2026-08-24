from unittest.mock import Mock

from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.collaboration import WriteRequestInfo, WriteRequestResult

def _manager(result):
    collab = Mock()
    collab.request_write.return_value = result
    collab.get_session.return_value = None
    return WriteTransactionManager(collab), collab

def test_request_path_is_explicit_acquiring_to_waiting():
    result = WriteRequestInfo(WriteRequestResult.WAITING, "req-1", 1)
    tx, _ = _manager(result)
    assert tx.start_editing() is False
    assert tx.state == WriteTransactionState.WAITING

def test_invalid_direct_idle_to_editing_transition_is_rejected():
    tx, _ = _manager(WriteRequestInfo(WriteRequestResult.REJECTED))
    assert tx._transition_to(WriteTransactionState.EDITING, "test") is False
    assert tx.state == WriteTransactionState.IDLE

def test_grant_failure_returns_to_waiting():
    tx, _ = _manager(WriteRequestInfo(WriteRequestResult.WAITING, "req-1", 1))
    tx.start_editing()
    assert tx.begin_grant() is True
    assert tx.state == WriteTransactionState.GRANTING
    tx.on_grant_failed()
    assert tx.state == WriteTransactionState.WAITING

def test_duplicate_waiting_start_does_not_request_write_twice():
    result = WriteRequestInfo(
        WriteRequestResult.WAITING,
        "req-1",
        1,
    )

    tx, collab = _manager(result)

    assert tx.start_editing() is False
    assert tx.state == WriteTransactionState.WAITING

    assert tx.start_editing() is False

    assert collab.request_write.call_count == 1
    assert tx.state == WriteTransactionState.WAITING


def test_duplicate_grant_is_idempotent_and_creates_one_snapshot(monkeypatch):
    result = WriteRequestInfo(
        WriteRequestResult.WAITING,
        "req-1",
        1,
    )

    tx, collab = _manager(result)

    collab.get_lock_generation.return_value = 7
    collab._sync_provider = None

    snapshot_calls = []

    monkeypatch.setattr(
        tx,
        "_create_snapshot",
        lambda: snapshot_calls.append("snapshot"),
    )

    tx.start_editing()

    tx.on_write_granted()
    tx.on_write_granted()

    assert tx.state == WriteTransactionState.EDITING
    assert tx.is_editing is True
    assert snapshot_calls == ["snapshot"]
    assert collab.get_session.call_count == 1


def test_duplicate_grant_failure_is_idempotent():
    result = WriteRequestInfo(WriteRequestResult.WAITING, "req-1", 1)
    tx, _ = _manager(result)

    tx.start_editing()
    assert tx.begin_grant() is True
    tx.on_grant_failed()
    tx.on_grant_failed()  # Duplicate failure notification.

    assert tx.state == WriteTransactionState.WAITING

