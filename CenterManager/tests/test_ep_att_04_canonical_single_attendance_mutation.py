from datetime import time
from types import SimpleNamespace

from centermanager.models.attendance import Attendance
from centermanager.services.attendance_service import AttendanceService


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
    def get_by_id(self, session_id):
        if session_id != 7:
            return None
        return SimpleNamespace(id=7, class_id=55, scheduled_date=None)


class _EnrollmentRepo:
    def exists(self, student_id, class_id):
        return student_id == 1 and class_id == 55


class _AttendanceRepo:
    def __init__(self, rows):
        self.rows = list(rows)

    def get_by_session(self, session_id):
        return [row for row in self.rows if row.session_id == session_id]

    def add(self, attendance):
        self.rows.append(attendance)
        return attendance

    def refresh(self, attendance):
        return attendance


class _Provider:
    def __init__(self, attendance_repo):
        self._attendance_repo = attendance_repo

    def sessions(self, session):
        return _SessionRepo()

    def enrollments(self, session):
        return _EnrollmentRepo()

    def attendance(self, session):
        return self._attendance_repo


class _Timeline:
    def __init__(self):
        self.events = []

    def log_event(self, **kwargs):
        self.events.append(kwargs)


def _service(existing):
    db_session = _FakeDbSession()
    repo = _AttendanceRepo([existing])
    service = AttendanceService(
        session_factory=lambda: db_session,
        timeline_service=_Timeline(),
        permission_service=None,
        repository_provider=_Provider(repo),
    )
    return service, db_session, repo


def test_att_04_legacy_single_row_api_delegates_to_atomic_boundary():
    service = object.__new__(AttendanceService)
    captured = {}
    marker = object()

    def atomic(session_id, rows, preserve_existing_optional_fields=False):
        captured["session_id"] = session_id
        captured["rows"] = rows
        captured["preserve"] = preserve_existing_optional_fields
        return [marker]

    service._save_session_attendance_atomic = atomic

    saved = AttendanceService.create_or_update_attendance.__wrapped__(
        service,
        session_id=7,
        student_id=1,
        status="Late",
        arrival_time="08:15",
        teacher_note="traffic",
    )

    assert saved is marker
    assert captured == {
        "session_id": 7,
        "rows": {
            1: {
                "status": "Late",
                "arrival_time": "08:15",
                "teacher_note": "traffic",
            }
        },
        "preserve": True,
    }


def test_att_04_legacy_none_values_preserve_existing_optional_fields():
    existing = Attendance(
        session_id=7,
        student_id=1,
        status="Absent",
        arrival_time=time(8, 10),
        teacher_note="existing note",
    )
    service, db_session, _ = _service(existing)

    saved = service._save_session_attendance_atomic(
        7,
        {
            1: {
                "status": "Present",
                "arrival_time": None,
                "teacher_note": None,
            }
        },
        preserve_existing_optional_fields=True,
    )

    assert saved == [existing]
    assert db_session.commits == 1
    assert db_session.rollbacks == 0
    assert existing.status == "Present"
    assert existing.arrival_time == time(8, 10)
    assert existing.teacher_note == "existing note"


def test_att_04_session_sheet_remains_authoritative_for_optional_field_clears():
    existing = Attendance(
        session_id=7,
        student_id=1,
        status="Absent",
        arrival_time=time(8, 10),
        teacher_note="existing note",
    )
    service, db_session, _ = _service(existing)

    saved = service._save_session_attendance_atomic(
        7,
        {
            1: {
                "status": "Present",
                "arrival_time": None,
                "teacher_note": None,
            }
        },
    )

    assert saved == [existing]
    assert db_session.commits == 1
    assert db_session.rollbacks == 0
    assert existing.status == "Present"
    assert existing.arrival_time is None
    assert existing.teacher_note is None
