"""EP-PROTOTYPE-07 — attendance and assessment boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "ui"


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_attendance_and_assessment_use_existing_service_boundaries():
    session_detail = _read("session/session_detail_dialog.py")
    attendance = _read("session/session_attendance_widget.py")
    assessment = _read("assessment/assessment_section.py")
    assessment_dialog = _read("assessment/assessment_dialog.py")

    assert "SessionAttendanceWidget" in session_detail
    assert "create_or_update_attendance" in attendance
    assert "AssessmentService" in assessment
    assert "create_assessment" in assessment_dialog
    assert "update_assessment" in assessment_dialog
    assert "AssessmentValidationError" in assessment_dialog


def test_student_attendance_remains_read_only():
    source = _read("student_workspace/student_attendance_widget.py")
    assert "NoEditTriggers" in source
    assert "create_or_update_attendance" not in source


def test_assessment_dialog_imports_qwidget_for_constructor_annotation():
    source = _read("assessment/assessment_dialog.py")
    assert "QMessageBox, QLabel, QWidget" in source
