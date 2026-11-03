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
