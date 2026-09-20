from datetime import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.attendance import Attendance
from centermanager.services.attendance_service import AttendanceService


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "src" / "centermanager" / "services" / "attendance_service.py"
UI_PATH = ROOT / "src" / "centermanager" / "ui" / "session" / "session_attendance_widget.py"
DETAIL_PATH = ROOT / "src" / "centermanager" / "ui" / "session" / "session_detail_dialog.py"


class _FakeDbSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _SessionRepo:
    def __init__(self, class_id=55):
        self._session = SimpleNamespace(id=7, class_id=class_id)

    def get_by_id(self, session_id):
        return self._session if session_id == self._session.id else None


class _EnrollmentRepo:
    def __init__(self, valid_student_ids):
        self.valid_student_ids = set(valid_student_ids)

    def exists(self, student_id, class_id):
        return class_id == 55 and student_id in self.valid_student_ids


class _AttendanceRepo:
    def __init__(self, existing=None):
        self.rows = list(existing or [])
        self.added = []

    def get_by_session(self, session_id):
        return [row for row in self.rows if row.session_id == session_id]

    def add(self, attendance):
        self.rows.append(attendance)
        self.added.append(attendance)
        return attendance

    def refresh(self, attendance):
        return attendance


class _Provider:
    def __init__(self, attendance_repo, valid_student_ids):
        self.session_repo = _SessionRepo()
        self.enrollment_repo = _EnrollmentRepo(valid_student_ids)
        self.attendance_repo = attendance_repo

    def sessions(self, session):
        return self.session_repo

    def enrollments(self, session):
        return self.enrollment_repo

    def attendance(self, session):
        return self.attendance_repo


class _Timeline:
    def __init__(self):
        self.events = []

    def log_event(self, **kwargs):
        self.events.append(kwargs)


def _service(db_session, attendance_repo, valid_student_ids):
    return AttendanceService(
        session_factory=lambda: db_session,
        timeline_service=_Timeline(),
        permission_service=None,
        repository_provider=_Provider(attendance_repo, valid_student_ids),
    )


def test_att_01_session_ui_uses_one_atomic_service_call():
    ui = UI_PATH.read_text(encoding="utf-8")
    detail = DETAIL_PATH.read_text(encoding="utf-8")

    assert "save_session_attendance(" in ui
    assert ".create_or_update_attendance(" not in ui
    assert "attendance_rows=attendance_rows" in ui
    assert "SessionAttendanceWidget" in detail


def test_att_01_batch_api_delegates_to_atomic_boundary_not_single_row_commits():
    source = SERVICE_PATH.read_text(encoding="utf-8")
    batch_source = source.split("def batch_update_attendance", 1)[1].split(
        '@require_permission("attendance.view")', 1
    )[0]

    assert "_save_session_attendance_atomic" in batch_source
    assert "create_or_update_attendance" not in batch_source
    assert "def save_session_attendance(" in source
    assert "attendance_repo.get_by_session(session_id)" in source
    assert "session.commit()" in source
    assert "session.rollback()" in source


def test_att_01_arrival_time_is_normalized_to_model_type():
    assert AttendanceService._normalize_arrival_time(None) is None
    assert AttendanceService._normalize_arrival_time("") is None
    assert AttendanceService._normalize_arrival_time("08:15") == time(8, 15)
    assert AttendanceService._normalize_arrival_time("08:15:30") == time(8, 15, 30)
    canonical = time(9, 5)
    assert AttendanceService._normalize_arrival_time(canonical) is canonical

    with pytest.raises(ValueError, match="Arrival time"):
        AttendanceService._normalize_arrival_time("25:99")


def test_att_01_invalid_late_row_rolls_back_without_mutating_earlier_row():
    existing = Attendance(
        session_id=7,
        student_id=1,
        status="Absent",
        arrival_time=None,
        teacher_note="old",
    )
    repo = _AttendanceRepo([existing])
    db_session = _FakeDbSession()
    service = _service(db_session, repo, valid_student_ids={1})

    with pytest.raises(ValueError, match="Student 2"):
        service._save_session_attendance_atomic(
            7,
            {
                1: {"status": "Present", "arrival_time": "08:00", "teacher_note": "changed"},
                2: {"status": "Present", "arrival_time": "08:05", "teacher_note": None},
            },
        )

    assert db_session.commits == 0
    assert db_session.rollbacks == 1
    assert existing.status == "Absent"
    assert existing.arrival_time is None
    assert existing.teacher_note == "old"
    assert repo.added == []


def test_att_01_successful_sheet_commits_once_and_persists_all_rows():
    existing = Attendance(
        session_id=7,
        student_id=1,
        status="Absent",
        arrival_time=None,
        teacher_note="old",
    )
    repo = _AttendanceRepo([existing])
    db_session = _FakeDbSession()
    service = _service(db_session, repo, valid_student_ids={1, 2})

    saved = service._save_session_attendance_atomic(
        7,
        {
            1: {"status": "Late", "arrival_time": "08:15", "teacher_note": "traffic"},
            2: {"status": "Present", "arrival_time": None, "teacher_note": None},
        },
    )

    assert db_session.commits == 1
    assert db_session.rollbacks == 0
    assert len(saved) == 2
    assert existing.status == "Late"
    assert existing.arrival_time == time(8, 15)
    assert existing.teacher_note == "traffic"
    assert len(repo.added) == 1
    assert repo.added[0].student_id == 2
    assert repo.added[0].status == "Present"
    assert repo.added[0].arrival_time is None
