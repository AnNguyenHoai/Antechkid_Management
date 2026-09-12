"""EP-ARCH-03.33 — SessionReportService RepositoryProvider boundary regression."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "session_report_service.py"


def test_session_report_service_uses_repository_provider_boundary():
    source = SERVICE.read_text(encoding="utf-8")

    assert "from centermanager.repositories.teacher_repository import TeacherRepository" not in source
    assert "from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider" in source
    assert "self._repository_provider.teachers(db_session)" in source
    assert "TeacherRepository(db_session)" not in source


def test_session_report_service_has_no_direct_persistence_operations():
    source = SERVICE.read_text(encoding="utf-8")
    for operation in (
        "db_session.query",
        "db_session.get",
        "db_session.add",
        "db_session.delete",
        "db_session.refresh",
    ):
        assert operation not in source, operation


def test_session_report_service_keeps_existing_constructor_compatibility():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session_service: SessionService" in source
    assert "generator: Optional[SessionReportGenerator] = None" in source
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
