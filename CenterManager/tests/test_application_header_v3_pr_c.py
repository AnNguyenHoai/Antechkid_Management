# -*- coding: utf-8 -*-
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from centermanager.ui.application_shell import ApplicationTopBar
from centermanager.ui.design_system.tokens import COMPONENT_METRICS


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


def test_header_keeps_routine_editing_state_in_fixed_header(app):
    top = ApplicationTopBar(user_name="An", role_name="Admin", runtime_version="v1", sync_status="idle")
    assert top.header.height() == COMPONENT_METRICS["app_top_bar_height"]
    assert top.state_zone.parent() is top.header
    assert top.mode_badge.parent() is top.state_zone
    assert top.transaction_label.parent() is top.state_zone
    assert top.start_edit_button.parent() is top.state_zone


def test_routine_start_finish_do_not_open_feedback_operation_row(app, monkeypatch):
    top = ApplicationTopBar(user_name="An")
    calls = []
    monkeypatch.setattr(top, "begin_operation", lambda *args, **kwargs: calls.append("begin"))
    monkeypatch.setattr(top, "finish_operation", lambda *args, **kwargs: calls.append("finish"))
    top.start_edit_requested.connect(lambda: None)
    top.start_edit_btn.click()
    assert calls == []


def test_header_state_change_has_lightweight_animation(app):
    top = ApplicationTopBar(user_name="An")
    assert top._state_animation.duration() == 180
    top.set_mode("WRITE", "success")
    assert top.mode_badge.text() == "Mode: WRITE"


def test_feedback_api_is_preserved_for_real_notifications(app):
    top = ApplicationTopBar(user_name="An")
    assert top.feedback_host is not None
    assert callable(top.notify_success)
    assert callable(top.notify_warning)
    assert callable(top.notify_error)


def test_pr_c_source_separates_routine_state_from_feedback():
    source = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui" / "application_shell.py"
    text = source.read_text(encoding="utf-8")
    body = text.split("def _run_edit_operation", 1)[1].split("def set_mode", 1)[0]
    assert "begin_operation(" not in body
    assert "finish_operation(" not in body
    assert "ApplicationTopBarStateZone" in text
    assert "QPropertyAnimation" in text
