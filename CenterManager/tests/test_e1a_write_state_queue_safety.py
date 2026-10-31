"""E1A safety regressions against isolated real Git authority/queue refs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.test_e0_write_recovery_audit import machines, clock  # noqa: F401
from centermanager.platform.collaboration import WriteRequestResult
from centermanager.platform.collaboration.write_queue import WriteRequest
from centermanager.platform.synchronization.lock_observation import observe_lock
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState


@pytest.mark.parametrize("offset,state", [(59, "ACTIVE"), (60, "GRACE"), (659, "GRACE"), (660, "RECLAIMABLE")])
def test_typed_lease_boundaries_keep_original_time_policy(offset, state):
    start = datetime(2026, 10, 31, 12)
    record = {"locked": True, "owner": "owner", "session_id": "session",
              "lease_expires_at": (start + timedelta(seconds=60)).isoformat()}
    assert observe_lock(record, now=start + timedelta(seconds=offset))["state"] == state
    assert observe_lock({"locked": False}, now=start)["state"] == "ABSENT"


@pytest.mark.parametrize("bad", [
    {"lease_expires_at": "bad"}, {"lease_expires_at": None},
    {"session_id": ""}, {"lease_revision": -1}, {"locked": "false"},
])
def test_invalid_lock_never_grants_or_releases(machines, bad):
    owner, provider = machines("owner")
    contender, other = machines("contender")
    record = owner._build_lock_data()
    record.update(bad)
    commit = provider._create_lock_commit_plumbing(record, None)
    assert provider._push_lock_branch(commit, None)
    assert provider.remote_lock_status()["state"] == "UNKNOWN"
    result = contender.request_write()
    assert result.result == WriteRequestResult.ERROR
    assert not contender.is_writing()
    assert not other.acquire_lock(contender._build_lock_data())
    assert provider._remote_lock_oid() == commit


def test_network_failure_is_unknown_not_absent_and_no_second_owner(machines, monkeypatch):
    owner, provider = machines("owner")
    contender, other = machines("contender")
    assert owner.request_write().is_granted
    original = other._run_git_command

    def disconnected(args, **kwargs):
        if args[0] == "ls-remote":
            raise RuntimeError("synthetic network outage")
        return original(args, **kwargs)

    monkeypatch.setattr(other, "_run_git_command", disconnected)
    assert contender.get_lock_status()["state"] == "UNKNOWN"
    assert contender.request_write().result == WriteRequestResult.ERROR
    assert not contender.is_writing()
    assert not other.acquire_lock(contender._build_lock_data())
    assert provider.remote_lock_status()["session_id"] == owner.get_session_id()


def test_missing_lock_json_is_unknown_not_available(machines):
    owner, provider = machines("owner")
    contender, _ = machines("contender")
    main = provider.get_remote_main_commit()
    assert provider._push_lock_branch(main, None)  # synthetic commit has no lock.json
    assert provider.remote_lock_status()["state"] == "UNKNOWN"
    assert contender.request_write().result == WriteRequestResult.ERROR
    assert not contender.is_writing()
    assert provider._remote_lock_oid() == main


def test_two_clients_concurrently_request_only_one_write_owner(machines):
    a, provider = machines("a")
    b, _ = machines("b")
    barrier = threading.Barrier(2)

    def request(manager):
        barrier.wait(timeout=10)
        return manager.request_write()

    with ThreadPoolExecutor(max_workers=2) as executor:
        fa = executor.submit(request, a)
        fb = executor.submit(request, b)
        results = [fa.result(timeout=60), fb.result(timeout=60)]
    assert sum(result.is_granted for result in results) == 1
    assert sum(manager.is_writing() for manager in (a, b)) == 1
    winner = a if a.is_writing() else b
    loser = b if a.is_writing() else a
    assert provider.remote_lock_status()["session_id"] == winner.get_session_id()
    assert loser.has_pending_waiting_request()


def test_approved_priority_still_precedes_fifo_among_equal_roles(machines):
    owner, _ = machines("owner")
    teacher, _ = machines("teacher")
    teacher.get_session().role = "teacher"
    admin, _ = machines("admin")
    assert owner.request_write().is_granted
    assert teacher.request_write().is_waiting
    assert owner.release_write()
    assert admin.request_write().is_granted  # canonical priority, not equal-priority bypass
    assert teacher.get_queue()["next"]["session_id"] == teacher.get_session_id()


@pytest.mark.parametrize("change", ["cancel", "expire"])
def test_request_cancelled_or_expired_after_lock_cas_never_becomes_write(machines, monkeypatch, clock, change):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    waiting = waiter.request_write()
    assert waiting.is_waiting
    assert owner.release_write()
    original = provider.acquire_lock

    def acquire_then_change(data):
        acquired = original(data)
        assert acquired
        if change == "cancel":
            assert provider.cancel_remote_write_request(waiting.request_id, waiter.get_session_id())
        else:
            clock.at(181)
        return acquired

    monkeypatch.setattr(provider, "acquire_lock", acquire_then_change)
    assert not waiter.grant_existing_waiting_request(waiting.request_id)
    assert not waiter.is_writing()
    assert provider.remote_lock_status()["state"] == "ABSENT"


def test_release_rejects_stale_oid_after_renewal_then_retries_safely(machines, monkeypatch):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    old = provider._remote_lock_oid()
    original = provider._delete_lock_branch
    raced = []

    def renew_before_delete(**kwargs):
        if not raced:
            raced.append(True)
            assert provider.renew_lock("owner", owner.get_session_id())
        return original(**kwargs)

    monkeypatch.setattr(provider, "_delete_lock_branch", renew_before_delete)
    assert not owner.release_write()
    assert owner.is_writing()
    assert provider._remote_lock_oid() != old
    assert not provider.release_lock("owner", session_id=owner.get_session_id(), expected_oid=old)
    assert owner.release_write()
    assert provider.remote_lock_status()["state"] == "ABSENT"


def test_username_without_bound_session_token_never_authorizes_release(machines):
    owner, provider = machines("owner", username="same")
    _, stranger = machines("stranger", username="same")
    assert owner.request_write().is_granted
    oid = provider._remote_lock_oid()
    assert not stranger.release_lock("same")
    assert not stranger.release_lock("force_release", session_id=owner.get_session_id())
    assert provider._remote_lock_oid() == oid


def test_lost_enqueue_response_keeps_visible_waiting_and_can_cancel(machines, monkeypatch):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    original = provider._push_queue_branch

    def lose_response(*args, **kwargs):
        assert original(*args, **kwargs)
        raise RuntimeError("synthetic lost enqueue acknowledgement")

    monkeypatch.setattr(provider, "_push_queue_branch", lose_response)
    transaction = WriteTransactionManager(waiter)
    assert not transaction.start_editing()
    assert transaction.state == WriteTransactionState.WAITING
    assert waiter._pending_request is not None
    assert provider.remote_queue_status()["length"] == 1
    assert not waiter.is_writing()
    monkeypatch.setattr(provider, "_push_queue_branch", original)
    assert transaction.cancel_editing()
    assert transaction.state == WriteTransactionState.IDLE
    assert provider.remote_queue_status()["length"] == 0


def test_lost_cancel_response_keeps_waiting_until_barrier_acknowledged(machines, monkeypatch):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    transaction = WriteTransactionManager(waiter)
    assert not transaction.start_editing()
    original = provider.cancel_remote_write_request

    def lose_response(*args, **kwargs):
        assert original(*args, **kwargs)
        raise RuntimeError("synthetic lost cancellation acknowledgement")

    monkeypatch.setattr(provider, "cancel_remote_write_request", lose_response)
    assert not transaction.cancel_editing()
    assert transaction.state == WriteTransactionState.WAITING
    assert waiter._cancel_pending
    assert provider.remote_queue_status()["length"] == 0
    assert not waiter.grant_existing_waiting_request()
    monkeypatch.setattr(provider, "cancel_remote_write_request", original)
    assert transaction.cancel_editing()
    assert transaction.state == WriteTransactionState.IDLE


def test_cancel_barrier_rejects_a_delayed_enqueue_push(machines):
    waiter, provider = machines("waiter")
    request = WriteRequest("delayed", waiter.get_session_id(), "waiter", "waiter", "admin", 100, datetime.now())
    delayed = provider._create_queue_commit_plumbing([request.to_dict()], None)
    waiter._pending_request = request  # enqueue response is unknown; candidate is in flight
    assert waiter.cancel_waiting_request()
    assert not provider._push_queue_branch(delayed, None)
    assert provider.remote_queue_status()["length"] == 0
    assert not waiter.is_writing()


def test_ungranted_lease_release_failure_retains_cleanup_and_blocks_other_grants(machines, monkeypatch):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    next_client, _ = machines("next")
    assert owner.request_write().is_granted
    request = waiter.request_write()
    assert owner.release_write()
    original_delete = provider._delete_lock_branch
    original_consume = provider.consume_remote_write_request
    monkeypatch.setattr(provider, "consume_remote_write_request", lambda *args: False)
    monkeypatch.setattr(provider, "_delete_lock_branch", lambda **kwargs: False)
    assert not waiter.grant_existing_waiting_request(request.request_id)
    assert waiter._ungranted_lock
    assert not waiter.is_writing()
    assert next_client.request_write().is_waiting
    assert not next_client.is_writing()
    monkeypatch.setattr(provider, "_delete_lock_branch", original_delete)
    monkeypatch.setattr(provider, "consume_remote_write_request", original_consume)
    assert waiter.refresh_waiting_request()
    assert not waiter._ungranted_lock
    assert waiter.grant_existing_waiting_request(request.request_id)


def test_unknown_authority_ui_does_not_say_no_active_editor(machines):
    from centermanager.ui.main_window import MainWindow
    from PySide6.QtWidgets import QLabel

    manager, _ = machines("client")
    manager.get_lock_status = lambda: {"state": "UNKNOWN", "locked": True}
    window = SimpleNamespace(_collaboration_manager=manager, _transaction=Mock(is_editing=False),
                             waiting_indicator=QLabel(), app_top_bar=Mock())
    MainWindow._update_waiting_status(window)
    assert "unknown" in window.waiting_indicator.text().lower()
    window.app_top_bar.set_editor_state.assert_called_with("Unable to verify WRITE authority", "warning")


def test_cancel_during_gui_handoff_records_intent_without_state_mutex_deadlock(machines):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    assert owner.request_write().is_granted
    request = waiter.request_write()
    assert owner.release_write()
    entered = threading.Event()
    proceed = threading.Event()

    def gui_guard():
        entered.set()
        assert proceed.wait(timeout=10)
        return True

    waiter.set_write_handoff_guard(gui_guard)
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = executor.submit(waiter.grant_existing_waiting_request, request.request_id)
        assert entered.wait(timeout=10)
        try:
            assert not waiter.cancel_waiting_request()
            assert waiter._cancel_pending
        finally:
            proceed.set()
        assert result.result(timeout=10) is False
    assert not waiter.is_writing()
    assert provider.remote_lock_status()["state"] == "ABSENT"
    assert waiter.cancel_waiting_request()


@pytest.mark.parametrize("accepted", [True, False])
def test_uncertain_renewal_keeps_exact_capability_for_safe_release_retry(machines, monkeypatch, accepted):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    original = provider._push_lock_branch

    def lost_renewal_response(*args, **kwargs):
        if accepted:
            assert original(*args, **kwargs)
        return False

    monkeypatch.setattr(provider, "_push_lock_branch", lost_renewal_response)
    assert not provider.renew_lock("owner", owner.get_session_id())
    monkeypatch.setattr(provider, "_push_lock_branch", original)
    assert owner.release_write()
    assert provider.remote_lock_status()["state"] == "ABSENT"


def test_repeated_rejected_renewals_do_not_forget_last_verified_release_token(machines, monkeypatch, clock):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    original_oid = provider._remote_lock_oid()
    original_push = provider._push_lock_branch
    monkeypatch.setattr(provider, "_push_lock_branch", lambda *args, **kwargs: False)
    for second in (1, 2, 3):
        clock.at(second)
        assert not provider.renew_lock("owner", owner.get_session_id())
    assert provider._remote_lock_oid() == original_oid
    monkeypatch.setattr(provider, "_push_lock_branch", original_push)
    assert owner.release_write()
    assert provider.remote_lock_status()["state"] == "ABSENT"


def test_deferred_grant_event_is_reconciled_through_authorized_transaction_flow(machines):
    from centermanager.ui.main_window import MainWindow
    from centermanager.platform.collaboration.poller import CollaborationSnapshot

    owner, _ = machines("owner")
    waiter, _ = machines("waiter")
    assert owner.request_write().is_granted
    transaction = WriteTransactionManager(waiter)
    assert not transaction.start_editing()
    request_id = transaction._waiting_request_id
    assert owner.release_write()
    assert waiter.grant_existing_waiting_request(request_id)
    # No WriteGranted handler was registered: emulate the signal arriving late.
    assert transaction.state == WriteTransactionState.WAITING
    snapshot = CollaborationSnapshot(remote_lock=waiter.get_lock_status(), queue=waiter.get_queue(),
                                     poll_status="success")
    window = SimpleNamespace(_collaboration_manager=waiter, _transaction=transaction,
                             _update_write_buttons=Mock(), statusBar=Mock())
    MainWindow._reconcile_waiting_transaction(window, snapshot)
    assert transaction.state == WriteTransactionState.EDITING
    assert not waiter.has_verified_waiting_grant("another-request")
    transaction.on_write_granted()  # a late/duplicate event is harmless
    assert transaction.state == WriteTransactionState.EDITING


def test_provisional_handoff_blocks_background_runtime_replacement(machines):
    from centermanager.platform.sync import RuntimeSyncService

    manager, _ = machines("client")
    manager._ungranted_lock = True
    assert not manager.is_writing()
    sync_manager, context = Mock(), Mock()
    context.get_context.return_value.runtime.is_ready.return_value = True
    sync_manager.provider.return_value.health.return_value = True
    service = RuntimeSyncService(sync_manager=sync_manager, collab_manager=manager, context_manager=context)
    service._current_version = 1
    service._remote_version = 2
    service._perform_sync = Mock()
    service._attempt_sync()
    service._perform_sync.assert_not_called()
    assert service._deferred_count == 1
