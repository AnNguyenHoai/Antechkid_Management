"""UI regression contract for explicit standalone Session completion CTA.

This PR depends on SessionService.complete_scheduled_session from #655.
No migrations, finance formulas, Git or Recovery changes.
"""
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src/centermanager"
DETAIL = ROOT / "ui/session/session_detail_dialog.py"
SCHEDULE = ROOT / "ui/class_workspace/class_schedule_widget.py"
SERVICE = ROOT / "services/session_service.py"


def _text(path):
    return path.read_text(encoding="utf-8")


def test_completion_banner_is_above_teaching_tabs_and_has_accessible_action():
    source = _text(DETAIL)
    assert 'self.complete_session_btn = QPushButton("✓  Hoàn thành buổi học")' in source
    assert 'self.complete_session_btn.setMinimumHeight(44)' in source
    assert source.index("main_layout.addWidget(completion_card)") < source.index(
        "main_layout.addWidget(self.tab_widget)"
    )
    assert 'self.complete_session_btn.clicked.connect(self._on_complete_session_clicked)' in source
    assert "self.completion_description.setWordWrap(True)" in source


def test_completed_and_ineligible_sessions_never_offer_action():
    source = _text(DETAIL)
    render = source.split("def refresh_completion_controls(", 1)[1].split(
        "def _on_complete_session_clicked(", 1
    )[0]
    assert 'self.complete_session_btn.hide()' in render
    assert 'if status == SessionStatus.COMPLETED.value:' in render
    assert 'self.completion_title.setText("✓  Đã hoàn thành buổi học")' in render
    assert 'if status != SessionStatus.SCHEDULED.value:' in render
    assert "effective_date > get_clock().today()" in render
    assert "not self._historical_read_only" in render
    assert "self.attendance_widget._can_write()" in render
    assert "self.complete_session_btn.setEnabled(can_write)" in render


def test_completion_requires_fresh_state_explicit_confirmation_and_live_write():
    source = _text(DETAIL)
    action = source.split("def _on_complete_session_clicked(", 1)[1].split(
        "def _update_attendance_summary(", 1
    )[0]
    assert 'self._session_service.get_session(self._session_id)' in action
    assert "current.status != SessionStatus.SCHEDULED.value" in action
    assert 'QMessageBox.StandardButton.No,' in action
    assert "answer != QMessageBox.StandardButton.Yes" in action
    assert action.count("self.attendance_widget._can_write()") >= 2
    assert "self._historical_read_only" in action
    assert "self._session_service.complete_scheduled_session(self._session_id)" in action
    assert "self._attendance_service.get_session_attendance_overview(" in action
    assert 'overview.get("Unmarked", 0)' in action
    assert "self.session_updated.emit()" in action


def test_existing_post_attendance_prompt_remains_independent():
    source = _text(DETAIL)
    attendance = _text(ROOT / "ui/session/session_attendance_widget.py")
    assert "def _on_attendance_changed(self)" in source
    assert "def _on_complete_session_clicked(self)" in source
    assert "complete_scheduled_session(" not in attendance
    assert "save_session_attendance(" in attendance
    assert "def complete_scheduled_session(" in _text(SERVICE)


def test_list_refresh_when_completion_changes_even_if_dialog_closes_with_x():
    source = _text(SCHEDULE)
    assert "dialog.refresh_completion_controls()" in source
    assert "dialog.session_updated.connect(self._load_sessions)" in source
    assert "dialog.session_updated.connect(lambda: self.session_updated.emit())" in source


def test_only_session_ui_code_and_contract_docs_may_change():
    source = _text(DETAIL)
    assert "TuitionAccrualService" not in source
    assert "monthly_tuition" not in source
    assert "update_session(" not in source.split("def _on_complete_session_clicked(", 1)[1].split(
        "def _update_attendance_summary(", 1
    )[0]
