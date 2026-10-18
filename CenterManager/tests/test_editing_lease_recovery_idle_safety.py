# -*- coding: utf-8 -*-
"""Regression coverage for stale/idle editing recovery safety."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from centermanager.platform.collaboration import WriteRequestInfo, WriteRequestResult
from centermanager.services.write_transaction import (
    WriteTransactionManager,
    WriteTransactionState,
)


class FakeProvider:
    def __init__(self):
        self.main = "a" * 40
        self.lock = {
            "locked": True,
            "session_id": "session-a",
            "owner": "user-a",
            "lease_expires_at": (datetime.now() + timedelta(seconds=60)).isoformat(),
        }
        self.renewed = True

    def get_remote_main_commit(self):
        return self.main

    def remote_lock_status(self):
        return dict(self.lock)

    def renew_lock(self, owner, session_id):
        if self.renewed:
            self.lock.update(
                locked=True,
                session_id=session_id,
                owner=owner,
                lease_expires_at=(datetime.now() + timedelta(seconds=60)).isoformat(),
            )
        return self.renewed


class FakeCollaboration:
    def __init__(self):
        self._sync_provider = FakeProvider()
        self._session = SimpleNamespace(session_id="session-a", username="user-a")
        self._writing = True
        self.suspended = False
        self.cleared = False
        self.released = False
        self.request_result = WriteRequestInfo(
            WriteRequestResult.GRANTED,
            request_id="recover",
            message="reacquired",
        )
        self.generation = 7

    def get_session(self):
        return self._session

    @staticmethod
    def _is_lease_valid(value):
        return bool(value and datetime.now() < datetime.fromisoformat(value))

    def suspend_write_lease_renewal(self):
        self.suspended = True

    def resume_write_lease_renewal(self):
        self.suspended = False

    def renew_remote_lease(self, force=False):
        assert force is True
        if not self._sync_provider.renewed:
            return False
        self.suspended = False
        return self._sync_provider.renew_lock(
            self._session.username,
            self._session.session_id,
        )

    def clear_local_write_projection_for_recovery(self):
        self.cleared = True
        self._writing = False
        self.suspended = False

    def request_write(self, reason=""):
        assert reason == "recover stale editing"
        if self.request_result.is_granted:
            self._writing = True
        return self.request_result

    def cancel_waiting_request(self):
        return True

    def get_lock_generation(self):
        return self.generation

    def is_writing(self):
        return self._writing

    def release_write(self):
        self.released = True
        self._writing = False
        self._sync_provider.lock = {
            "locked": False,
            "session_id": None,
            "owner": None,
            "lease_expires_at": None,
        }
        return True


def _editing_transaction():
    collab = FakeCollaboration()
    tx = WriteTransactionManager(collab)
    tx._state = WriteTransactionState.EDITING
    tx._is_editing = True
    tx._session = collab.get_session()
    tx._base_main_commit = collab._sync_provider.main
    tx._expected_generation = collab.generation
    return tx, collab


def test_lease_loss_pauses_editing_and_disables_transaction_write_state():
    tx, collab = _editing_transaction()

    assert tx.pause_editing_for_lost_authority("renewal failed") is True

    assert tx.state == WriteTransactionState.EDITING_STALE
    assert tx.is_editing is False
    assert collab.suspended is True
    assert "renewal failed" in tx.stale_editing_reason


def test_stale_editing_recovers_existing_same_session_lease_without_resetting_work():
    tx, collab = _editing_transaction()
    tx.mark_dirty()
    tx.pause_editing_for_lost_authority("temporary renewal failure")

    assert tx.recover_stale_editing() is True

    assert tx.state == WriteTransactionState.EDITING
    assert tx.is_editing is True
    assert tx.has_changes is True
    assert collab.suspended is False
    assert collab.cleared is False


def test_expired_lease_is_reacquired_without_repository_pull_when_main_is_unchanged():
    tx, collab = _editing_transaction()
    tx.mark_dirty()
    tx.pause_editing_for_lost_authority("lease expired")
    collab._sync_provider.lock["lease_expires_at"] = (
        datetime.now() - timedelta(seconds=5)
    ).isoformat()

    assert tx.recover_stale_editing() is True

    assert collab.cleared is True
    assert tx.has_changes is True
    assert tx.state == WriteTransactionState.EDITING


def test_recovery_fails_closed_when_main_changed_while_editor_was_stale():
    tx, collab = _editing_transaction()
    tx.mark_dirty()
    tx.pause_editing_for_lost_authority("lease expired")
    collab._sync_provider.main = "b" * 40

    assert tx.recover_stale_editing() is False

    assert tx.state == WriteTransactionState.PUBLISH_CONFLICT
    assert tx.is_editing is False
    assert "MAIN changed" in tx.last_start_error


def test_clean_idle_session_releases_write_immediately():
    tx, collab = _editing_transaction()

    assert tx.pause_editing_for_idle_timeout() is True

    assert tx.state == WriteTransactionState.EDITING_STALE
    assert collab.released is True


def test_dirty_idle_session_preserves_local_work_and_suspends_renewal():
    tx, collab = _editing_transaction()
    tx.mark_dirty()

    assert tx.pause_editing_for_idle_timeout() is True

    assert tx.state == WriteTransactionState.EDITING_STALE
    assert tx.has_changes is True
    assert collab.released is False
    assert collab.suspended is True


def test_main_window_no_longer_mutates_transaction_private_state_for_recovery():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "centermanager"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    start_handler = source.split("def _on_start_editing", 1)[1].split(
        "def _on_finish_editing", 1
    )[0]
    assert "recover_stale_editing()" in start_handler
    assert "._state = WriteTransactionState.IDLE" not in start_handler
    assert "._base_main_commit = None" not in start_handler
