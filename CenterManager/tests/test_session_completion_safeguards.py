"""Regression contract: Attendance save and Session completion remain separate."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.ui.class_workspace.class_schedule_widget import ClassScheduleWidget
from centermanager.services.tuition_policy import BillableSessionPolicy


ROOT = Path(__file__).resolve().parents[1] / "src/centermanager"


def _session(number, when, status):
    return SimpleNamespace(
        id=number, class_id=1, session_number=number,
        scheduled_date=when, actual_date=None, status=status,
    )


def test_warning_only_overdue_scheduled_sessions_independent_of_creation_order():
    sessions = [
        _session(7, date(2026, 10, 24), "Scheduled"),
        _session(8, date(2026, 10, 25), "Completed"),
        _session(9, date(2026, 10, 31), "Cancelled"),
        _session(10, date(2026, 11, 1), "Postponed"),
        _session(11, date(2026, 11, 15), "Scheduled"),
        _session(2, date(2026, 10, 4), "Scheduled"),
    ]
    warning = ClassScheduleWidget.incomplete_past_sessions(
        sessions, date(2026, 11, 11)
    )
    assert [x.session_number for x in warning] == [2, 7]
    assert [x.session_number for x in ClassScheduleWidget.incomplete_past_sessions(
        list(reversed(sessions)), date(2026, 11, 11)
    )] == [2, 7]


def test_completed_session_is_not_warning_and_scheduled_session_is_not_billable():
    enrollment = SimpleNamespace(
        class_id=1, enrolled_from_session=1, enrolled_until_session=12,
        withdrawn_from_session=None, end_date=None, freezes=[],
        billing_policy_version="attendance_v2",
    )
    overdue = _session(7, date(2026, 10, 24), "Scheduled")
    assert not BillableSessionPolicy.is_billable(overdue, enrollment, "Present")
    overdue.status = "Completed"
    assert BillableSessionPolicy.is_billable(overdue, enrollment, "Present")
    assert ClassScheduleWidget.incomplete_past_sessions([overdue], date(2026, 11, 11)) == []


def test_attendance_save_first_then_separate_opt_in():
    attendance = (ROOT / "ui/session/session_attendance_widget.py").read_text(encoding="utf-8")
    detail = (ROOT / "ui/session/session_detail_dialog.py").read_text(encoding="utf-8")
    assert "save_session_attendance(" in attendance
    assert "self.attendance_changed.emit()" in attendance
    assert "def _on_attendance_changed" in detail
    assert "complete_scheduled_session(self._session_id)" in detail
    assert "QMessageBox.StandardButton.No," in detail
    # Never auto-complete during primary attendance persistence.
    assert "complete_scheduled_session" not in attendance
    assert detail.index("answer = QMessageBox.question(") < detail.index(
        "complete_scheduled_session(self._session_id)"
    )


def test_domain_completion_is_permission_gated_and_checks_current_state():
    session = (ROOT / "services/session_service.py").read_text(encoding="utf-8")
    method = session.split("def complete_scheduled_session(", 1)[1].split(
        '    @require_permission("lesson.update")\n    def update_session(', 1
    )[0]
    assert 'session_obj.status != SessionStatus.SCHEDULED.value' in method
    assert 'self._require_active_class(db_session, session_obj.class_id)' in method
    assert "get_clock().today()" in method
    assert "record_for_active_write(" in method
    assert "db_session.commit()" in method
    assert "self._publish_class_session_changed(" in method
    assert '@require_permission("lesson.update")\n    def complete_scheduled_session' in session


def test_no_finance_or_migration_change_in_completion_feature():
    # Formula belongs exclusively to the existing BillableSessionPolicy.
    source = (ROOT / "ui/class_workspace/class_schedule_widget.py").read_text(encoding="utf-8")
    assert "TuitionAccrualService" not in source
    assert "finance_period" not in source
