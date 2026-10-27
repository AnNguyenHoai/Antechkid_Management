# -*- coding: utf-8 -*-
"""Regression contracts for notifying the active WRITE holder about queued requests."""
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from centermanager.ui.application_shell import ApplicationTopBar


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_header_shows_single_waiter_to_active_editor(app):
    top = ApplicationTopBar(user_name="Holder")
    top.set_mode("WRITE", "success")
    top.set_transaction_text("Editing")
    top.set_waiting_requests(1, "Hoàng Việt")

    assert top.waiting_request_badge.isVisible()
    assert top.waiting_request_badge.text() == "1 waiting"
    assert "Hoàng Việt is waiting for editing access" in top.guidance_panel.label.text()
    assert "Finish editing" in top.guidance_panel.label.text()


def test_header_summarizes_multiple_waiters_and_next_user(app):
    top = ApplicationTopBar(user_name="Holder")
    top.set_mode("WRITE", "success")
    top.set_transaction_text("Editing")
    top.set_waiting_requests(3, "Nguyễn An")

    assert top.waiting_request_badge.text() == "3 waiting"
    assert "3 users are waiting for editing access" in top.guidance_panel.label.text()
    assert "Next: Nguyễn An" in top.guidance_panel.label.text()


def test_header_clears_waiter_notice_when_queue_is_empty(app):
    top = ApplicationTopBar(user_name="Holder")
    top.set_mode("WRITE", "success")
    top.set_transaction_text("Editing")
    top.set_waiting_requests(1, "User B")
    top.set_waiting_requests(0)

    assert not top.waiting_request_badge.isVisible()
    assert "After changing data" in top.guidance_panel.label.text()


def test_main_window_projects_snapshot_queue_instead_of_discarding_it():
    source = _source("main_window.py")

    assert "self._apply_poller_snapshot(snapshot)" in source
    assert "self._project_holder_waiting_requests(snapshot)" in source
    assert "queue = snapshot.queue or {}" in source
    assert 'request.get("session_id") != current_session' in source
    assert "self.app_top_bar.set_waiting_requests(count, next_username)" in source


def test_holder_notice_is_read_only_projection_and_does_not_change_arbitration():
    source = _source("main_window.py")
    start = source.index("def _project_holder_waiting_requests")
    end = source.index("def _on_lease_renewal_failed", start)
    body = source[start:end]

    assert "request_write(" not in body
    assert "grant_existing_waiting_request(" not in body
    assert "release_write(" not in body
    assert "cancel_waiting_request(" not in body
    assert "snapshot.queue" in body


def test_idle_state_clears_stale_holder_waiter_notice():
    source = _source("main_window.py")
    start = source.index("def _update_write_buttons")
    end = source.index("def _update_waiting_status", start)
    body = source[start:end]

    assert 'if state == WriteTransactionState.IDLE:' in body
    assert "self.app_top_bar.set_waiting_requests(0)" in body
    assert "self._last_holder_waiting_request_count = 0" in body
