import inspect

from centermanager.repositories.provider import SqlAlchemyRepositoryProvider
from centermanager.services.attendance_service import AttendanceService


class _SessionContext:
    def __init__(self, session):
        self._session = session

    def __enter__(self):
        return self._session

    def __exit__(self, exc_type, exc, tb):
        return False


class _Session:
    pass


class _SessionRepository:
    def get_by_id(self, session_id):
        return type("SessionRecord", (), {"class_id": 42})()


class _EnrollmentRepository:
    def exists(self, student_id, class_id):
        return student_id == 7 and class_id == 42


class _AttendanceRepository:
    pass


class _Provider:
    def __init__(self):
        self.session_calls = []
        self.enrollment_calls = []
        self.attendance_calls = []

    def sessions(self, session):
        self.session_calls.append(session)
        return _SessionRepository()

    def enrollments(self, session):
        self.enrollment_calls.append(session)
        return _EnrollmentRepository()

    def attendance(self, session):
        self.attendance_calls.append(session)
        return _AttendanceRepository()


def test_attendance_service_does_not_select_concrete_repository_implementations():
    source = inspect.getsource(AttendanceService)

    assert "from centermanager.repositories.attendance_repository" not in source
    assert "from centermanager.repositories.enrollment_repository" not in source
    assert "from centermanager.repositories.session_repository" not in source
    assert "AttendanceRepository(" not in source
    assert "EnrollmentRepository(" not in source
    assert "SessionRepository(" not in source


def test_attendance_service_uses_injected_repository_provider_for_enrollment_check():
    provider = _Provider()
    session = _Session()
    service = AttendanceService(
        session_factory=lambda: _SessionContext(session),
        timeline_service=object(),
        permission_service=object(),
        repository_provider=provider,
    )

    assert service._check_student_enrolled(7, 123) is True
    assert service._check_student_enrolled(8, 123) is False
    assert provider.session_calls == [session, session]
    assert provider.enrollment_calls == [session, session]


def test_production_provider_exposes_all_current_repository_seams():
    provider = SqlAlchemyRepositoryProvider()

    for name in ("audit_logs", "class_timeline", "attendance", "enrollments", "sessions"):
        assert callable(getattr(provider, name))
