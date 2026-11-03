"""WRITE-HANDOFF-01: a queue-head without an editor reports why Git grant stalls.

All remote Git repos are disposable bare fixtures from the existing E0 suite.
"""
from tests.test_e0_write_recovery_audit import machines, clock  # noqa: F401
from centermanager.platform.collaboration.poller import CollaborationPoller


def test_queue_head_git_acquisition_failure_is_observable_then_recovers(machines, monkeypatch):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    request = waiter.request_write()
    assert request.is_waiting
    assert owner.release_write()
    assert waiter.get_lock_status()["state"] == "ABSENT"
    assert waiter.get_queue()["next"]["session_id"] == waiter.get_session_id()

    real_acquire = provider.acquire_lock
    monkeypatch.setattr(provider, "acquire_lock", lambda data: False)
    monkeypatch.setattr(provider, "last_lock_failure_was_contention", lambda: False)
    assert waiter.grant_existing_waiting_request(request.request_id) is False
    assert waiter.get_waiting_handoff_code() == "GIT_LOCK_ACQUISITION_FAILED"
    assert not waiter.is_writing()
    assert waiter.get_queue()["next"]["request_id"] == request.request_id

    monkeypatch.setattr(provider, "acquire_lock", real_acquire)
    assert waiter.grant_existing_waiting_request(request.request_id)
    assert waiter.get_waiting_handoff_code() == ""
    assert waiter.is_writing()
    assert waiter.get_lock_status()["session_id"] == waiter.get_session_id()


def test_queue_head_auto_handoff_logs_diagnostic_without_auto_grant(machines, monkeypatch, caplog):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    request = waiter.request_write()
    assert request.is_waiting
    assert owner.release_write()
    monkeypatch.setattr(provider, "acquire_lock", lambda data: False)
    monkeypatch.setattr(provider, "last_lock_failure_was_contention", lambda: False)

    poller = CollaborationPoller(waiter)
    poller._running = True
    try:
        poller._try_handoff_waiting_request(waiter.get_lock_status(), waiter.get_queue())
    finally:
        poller._running = False
    assert not waiter.is_writing()
    assert waiter.get_queue()["next"]["request_id"] == request.request_id
    assert waiter.get_waiting_handoff_code() == "GIT_LOCK_ACQUISITION_FAILED"
    assert "Automatic WRITE handoff deferred: reason=GIT_LOCK_ACQUISITION_FAILED" in caplog.text


def test_grace_never_grants_waiting_queue_head(machines, clock):
    owner, provider = machines("owner")
    waiter, _ = machines("waiter")
    assert owner.request_write().is_granted
    request = waiter.request_write()
    assert request.is_waiting
    clock.at(61)
    assert waiter.get_lock_status()["state"] == "GRACE"
    poller = CollaborationPoller(waiter)
    poller._running = True
    try:
        poller._try_handoff_waiting_request(waiter.get_lock_status(), waiter.get_queue())
    finally:
        poller._running = False
    assert not waiter.is_writing()
    assert waiter.get_queue()["next"]["request_id"] == request.request_id


def test_successful_empty_remote_queue_observation_reconciles_waiting_to_idle():
    """If Git's authoritative queue is empty, UI cannot keep position 1."""
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from centermanager.ui.main_window import MainWindow
    from centermanager.platform.collaboration.poller import CollaborationSnapshot
    from centermanager.services.write_transaction import WriteTransactionState

    calls = []
    now = datetime.now()
    tx = SimpleNamespace(
        state=WriteTransactionState.WAITING,
        _waiting_request_id="req-local",
        get_waiting_started_at=lambda: now - timedelta(seconds=15),
        begin_grant=lambda: calls.append("grant"),
        on_write_granted=lambda: calls.append("write"),
        cancel_waiting=lambda message: calls.append("cancel"),
    )
    class Collab:
        def get_session_id(self): return "local-session"
        def has_verified_waiting_grant(self, request_id): return False
        def reconcile_waiting_request(self, request_id):
            calls.append("remote-ack")
            return True

    window = SimpleNamespace(
        _transaction=tx,
        _collaboration_manager=Collab(),
        statusBar=lambda: SimpleNamespace(showMessage=lambda *args: None),
        _update_write_buttons=lambda: calls.append("refresh-ui"),
    )
    snapshot = CollaborationSnapshot(
        observation_started_at=now,
        poll_status="success",
        is_stale=False,
        queue={"length": 0, "requests": [], "next": None},
        remote_lock={"state": "ABSENT", "locked": False},
    )
    MainWindow._reconcile_waiting_transaction(window, snapshot)
    assert calls == ["remote-ack", "cancel", "refresh-ui"]


def test_unchanged_empty_git_snapshot_still_reaches_waiting_reconciler(machines):
    """Enqueue+cancel can happen between polls; a pending UI needs fresh ACK."""
    manager, _ = machines("local-user")
    poller = CollaborationPoller(manager)
    observed = []
    poller.snapshot_changed.connect(lambda snapshot: observed.append(snapshot))
    poller._running = True
    try:
        poller._poll()
        assert len(observed) == 1
        # Simulate local WAITING intent whose short-lived remote request has
        # already been removed before the next remote observation.
        manager._pending_request = object()
        poller._poll()
        assert len(observed) == 2
        assert observed[-1].queue.get("requests") == []
        assert observed[-1].remote_lock["state"] == "ABSENT"
        # Unchanged remote data without local WAITING should not trigger
        # repeated reconciliation work or redundant UI updates.
        manager._pending_request = None
        poller._poll()
        assert len(observed) == 2
    finally:
        poller._running = False
