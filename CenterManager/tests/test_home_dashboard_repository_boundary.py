"""EP-ARCH-03.29 - HomeDashboardService repository boundary contract."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "home_dashboard_service.py"


def test_home_dashboard_uses_repository_provider_and_not_concrete_repositories():
    source = SERVICE.read_text(encoding="utf-8")
    assert "from centermanager.repositories.provider import" in source
    assert "StudentRepository" not in source
    assert "ParentRepository" not in source
    assert "AssessmentRepository" not in source
    assert "session.query(" not in source


def test_home_dashboard_keeps_injected_provider_dependency():
    source = SERVICE.read_text(encoding="utf-8")
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
    for factory in (
        "students", "parents", "assessments", "classes", "sessions", "teachers", "employees",
    ):
        assert f"self._repository_provider.{factory}(session)" in source
