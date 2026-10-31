# -*- coding: utf-8 -*-
"""Regression coverage for first-request WAITING UI race."""
from datetime import datetime

from centermanager.platform.collaboration import WriteRequestInfo, WriteRequestResult
from centermanager.services.write_transaction import (
    WriteTransactionManager,
    WriteTransactionState,
)
from centermanager.platform.collaboration.poller import CollaborationSnapshot


class _LocalCollab:
    _sync_provider = None

    def __init__(self):
        self._session = type(
            "Session",
            (),
            {"session_id": "session-b", "username": "User B"},
        )()

    def request_write(self):
        return WriteRequestInfo(
            WriteRequestResult.WAITING,
            request_id="req-b",
            position=1,
            message="Waiting (position 1)",
        )

    def get_session(self):
        return self._session

    def get_session_id(self):
        return self._session.session_id


def test_first_waiting_request_records_causal_start_time():
    tx = WriteTransactionManager(_LocalCollab())

    assert tx.start_editing() is False
    assert tx.state == WriteTransactionState.WAITING
    assert tx.get_waiting_position() == 1
    assert tx.get_waiting_started_at() is not None


def test_collaboration_snapshot_exposes_observation_start_time():
    started = datetime.now()
    snapshot = CollaborationSnapshot(
        observation_started_at=started,
        poll_status="success",
    )
    assert snapshot.observation_started_at == started


def test_waiting_reconcile_rejects_pre_request_snapshot_contract():
    from pathlib import Path

    source = Path(
        "src/centermanager/ui/main_window.py"
    ).read_text(encoding="utf-8")
    start = source.index("def _reconcile_waiting_transaction")
    end = source.index("def _project_holder_waiting_requests", start)
    body = source[start:end]

    assert "get_waiting_started_at()" in body
    assert "observation_started_at < waiting_started_at" in body
    assert "Ignoring pre-request collaboration snapshot while WAITING" in body


def test_waiting_ui_uses_top_bar_without_duplicate_bottom_message():
    from pathlib import Path

    source = Path(
        "src/centermanager/ui/main_window.py"
    ).read_text(encoding="utf-8")

    buttons_start = source.index("def _update_write_buttons")
    buttons_end = source.index("def _update_lock_owner_display", buttons_start)
    buttons = source[buttons_start:buttons_end]

    waiting_start = buttons.index(
        "elif state == WriteTransactionState.WAITING:"
    )
    editing_start = buttons.index("elif is_editing:", waiting_start)
    waiting_block = buttons[waiting_start:editing_start]

    assert 'f"Waiting (pos {pos}) - {owner}"' in waiting_block
    assert "statusBar().showMessage" not in waiting_block
    assert "statusBar().clearMessage()" in waiting_block

    start_handler = source[
        source.index("def _on_start_editing"):
        source.index("def _on_finish_editing")
    ]
    assert "elif self._transaction.state == WriteTransactionState.WAITING:" in start_handler
    assert "self.statusBar().clearMessage()" in start_handler
