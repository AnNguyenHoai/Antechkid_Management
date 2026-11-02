"""S-01 Student Overview projection and UI contract tests."""
import ast
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.student_overview_service import StudentOverviewService

SRC = Path(__file__).resolve().parents[1] / "src" / "centermanager"


def student(sid, status="ACTIVE"):
    return SimpleNamespace(
        id=sid, student_code=f"ST{sid}", full_name=f"Student {sid}",
        status=status, deleted_at=None,
    )


def debt(sid, amount):
    return SimpleNamespace(student_id=sid, debt_amount=amount)


def test_compose_keeps_empty_month_and_archived_students():
    rows = StudentOverviewService.compose(
        [student(1), student(2, "ARCHIVED")],
        [{"student_id": 1, "class_name": "Python", "required": 4,
          "present": 2, "absent": 1, "missing": 1}],
        [debt(1, 120000), debt(1, 50000), debt(2, 60000)]
    )
    assert len(rows) == 2
    assert rows[0]["attendance_rate"] == 50
    assert rows[0]["debt"] == 170000
    assert rows[0]["missing"] == 1
    assert rows[1]["attendance_rate"] is None
    assert rows[1]["status"] == "ARCHIVED"
    assert rows[1]["debt"] == 60000


def test_compose_two_classes_uses_total_due_sessions():
    rows = StudentOverviewService.compose(
        [student(1)],
        [{"student_id": 1, "class_name": "Python", "required": 4,
          "present": 3, "absent": 1, "missing": 0},
         {"student_id": 1, "class_name": "Scratch", "required": 2,
          "present": 1, "absent": 0, "missing": 1}],
        [], {1: {"Python", "Scratch"}}
    )
    assert rows[0]["due"] == 6
    assert rows[0]["attendance_rate"] == 66.7
    assert rows[0]["classes"] == "Python, Scratch"
    assert rows[0]["monthly_classes"] == "Python, Scratch"


def test_new_ui_integrated_and_read_only():
    shell = (SRC / "ui/student_workspace/student_workspace_shell.py").read_text(encoding="utf-8")
    page = (SRC / "ui/student_workspace/student_overview_page.py").read_text(encoding="utf-8")
    service = (SRC / "services/student_overview_service.py").read_text(encoding="utf-8")
    for source in (shell, page, service):
        ast.parse(source)
    assert '"id": "overview"' in shell
    assert 'self.overview_page.refresh()' in shell
    assert 'get_outstanding_page(' in service
    assert 'VIEW_OPEN_RECEIVABLES' in service
    assert 'include_all=True' in service
    assert 'db.commit(' not in service
    assert 'db.query(' not in service
    assert 'set_server_data(' in page
