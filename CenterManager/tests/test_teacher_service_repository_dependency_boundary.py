"""Regression coverage for the EP-ARCH-03 TeacherService boundary."""
from pathlib import Path


SERVICE = Path("src/centermanager/services/teacher_service.py").read_text(encoding="utf-8")


def test_teacher_service_uses_repository_provider():
    assert "from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider" in SERVICE
    assert "repository_provider: Optional[RepositoryProvider] = None" in SERVICE
    assert "self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()" in SERVICE


def test_teacher_service_does_not_construct_concrete_repository():
    assert "from centermanager.repositories.teacher_repository import TeacherRepository" not in SERVICE
    assert "TeacherRepository(session)" not in SERVICE
    assert "self._repository_provider.teachers(session)" in SERVICE


def test_teacher_service_routes_all_teacher_repository_access_through_provider():
    assert SERVICE.count("self._repository_provider.teachers(session)") >= 9
