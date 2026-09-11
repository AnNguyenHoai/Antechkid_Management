from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

from centermanager.services.enrollment_service import EnrollmentService, EnrollmentStatus


class _FakeRepositoryProvider:
    def __init__(self, enrollment_repo, class_repo, student_repo):
        self.enrollment_repo = enrollment_repo
        self.class_repo = class_repo
        self.student_repo = student_repo
        self.calls = []

    def enrollments(self, session):
        self.calls.append(("enrollments", session))
        return self.enrollment_repo

    def classes(self, session):
        self.calls.append(("classes", session))
        return self.class_repo

    def students(self, session):
        self.calls.append(("students", session))
        return self.student_repo


def _session_factory(session):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = None
    return MagicMock(return_value=context)


def test_enrollment_service_uses_injected_repository_provider():
    session = MagicMock()
    class_obj = SimpleNamespace(
        id=10,
        name="Robotics A",
        course="Robotics",
        capacity=None,
        start_date=date(2026, 9, 1),
        deleted_at=None,
    )
    student = SimpleNamespace(id=7, deleted_at=None)
    enrollment_repo = MagicMock()
    enrollment_repo.exists.return_value = False
    enrollment_repo.get_active_by_class.return_value = []
    class_repo = MagicMock()
    class_repo.get_by_id.return_value = class_obj
    student_repo = MagicMock()
    student_repo.get_by_id.return_value = student

    provider = _FakeRepositoryProvider(enrollment_repo, class_repo, student_repo)
    service = EnrollmentService(_session_factory(session), repository_provider=provider)

    result = service.enroll(7, 10)

    assert result.student_id == 7
    assert result.class_id == 10
    assert result.status == EnrollmentStatus.ACTIVE.value
    assert provider.calls == [
        ("classes", session),
        ("students", session),
        ("enrollments", session),
    ]
    enrollment_repo.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(result)


def test_enrollment_transition_uses_injected_repositories():
    session = MagicMock()
    enrollment = SimpleNamespace(
        id=21,
        student_id=7,
        class_id=10,
        status=EnrollmentStatus.ACTIVE.value,
        end_date=None,
    )
    class_obj = SimpleNamespace(id=10, deleted_at=None)
    enrollment_repo = MagicMock()
    enrollment_repo.get_by_id.return_value = enrollment
    class_repo = MagicMock()
    class_repo.get_by_id.return_value = class_obj
    provider = _FakeRepositoryProvider(enrollment_repo, class_repo, MagicMock())
    service = EnrollmentService(_session_factory(session), repository_provider=provider)

    result = service.withdraw(21, end_date=date(2026, 9, 10))

    assert result is enrollment
    assert enrollment.status == EnrollmentStatus.WITHDRAWN.value
    assert enrollment.end_date == date(2026, 9, 10)
    assert provider.calls == [
        ("enrollments", session),
        ("classes", session),
    ]
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(enrollment)


def test_enrollment_service_default_provider_remains_compatible():
    service = EnrollmentService(MagicMock())

    assert service._repository_provider.__class__.__name__ == "SqlAlchemyRepositoryProvider"
