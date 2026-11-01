"""A-02 monthly attendance exceptions: boundary, CSV and UI contracts."""
import ast
import csv
import io
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.models.session import SessionStatus
from centermanager.services.monthly_attendance_exception_service import MonthlyAttendanceExceptionService

BASE = Path(__file__).resolve().parents[1] / "src" / "centermanager"


def lesson(status, scheduled, actual=None):
    return SimpleNamespace(status=status, scheduled_date=scheduled, actual_date=actual)


def test_due_excludes_future_and_cancelled_or_postponed():
    cutoff = date(2026, 10, 20)
    assert MonthlyAttendanceExceptionService._is_due(
        lesson(SessionStatus.COMPLETED.value, date(2026, 10, 1)), cutoff
    )
    assert not MonthlyAttendanceExceptionService._is_due(
        lesson(SessionStatus.SCHEDULED.value, date(2026, 10, 21)), cutoff
    )
    for status in (SessionStatus.CANCELLED.value, SessionStatus.POSTPONED.value):
        assert not MonthlyAttendanceExceptionService._is_due(
            lesson(status, date(2026, 10, 2)), cutoff
        )


def test_csv_has_distinct_presence_and_recording_columns():
    row = dict(
        student_code="ST01", student_name="Sample", class_name="Python",
        required=8, recorded=6, present=5, late=0, absent=1, excused=0,
        missing=2, attendance_rate=62.5, recording_rate=75,
    )
    result = list(csv.DictReader(io.StringIO(MonthlyAttendanceExceptionService.to_csv([row]))))
    assert len(result) == 1
    assert result[0]["Attendance Rate (%)"] == "62.5"
    assert result[0]["Recording Completeness (%)"] == "75"
    assert result[0]["Missing Records"] == "2"


def test_class_navigation_and_export_are_read_only():
    shell = (BASE / "ui" / "class_workspace" / "class_workspace_shell.py").read_text(encoding="utf-8")
    page = (BASE / "ui" / "class_workspace" / "monthly_attendance_exceptions_page.py").read_text(encoding="utf-8")
    service = (BASE / "services" / "monthly_attendance_exception_service.py").read_text(encoding="utf-8")
    for src in (shell, page, service):
        ast.parse(src)
    assert '"id": "monthly_attendance"' in shell
    assert 'self.monthly_attendance_page.refresh()' in shell
    assert "def export_csv(self):" in page
    assert "self._service.list_rows(" in page
    assert "encoding=\"utf-8-sig\"" in page
    assert "AttendanceService._roster_students_for_session" in service
    assert "db.commit(" not in service and "db.flush(" not in service
