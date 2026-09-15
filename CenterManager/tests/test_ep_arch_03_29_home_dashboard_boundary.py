"""EP-ARCH-03.29 - HomeDashboardService repository boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "home_dashboard_service.py"


def test_home_dashboard_uses_repository_provider():
    source = SERVICE.read_text(encoding="utf-8")
    assert "from centermanager.repositories.provider import" in source
    for concrete in ("StudentRepository", "ParentRepository", "AssessmentRepository"):
        assert concrete not in source
    assert "session.query(" not in source
    assert "session.get(" not in source


def test_home_dashboard_uses_provider_for_all_dashboard_aggregates():
    source = SERVICE.read_text(encoding="utf-8")
    for factory in ("students", "parents", "assessments", "classes", "sessions", "teachers", "employees"):
        assert f"self._repository_provider.{factory}(session)" in source


def test_home_dashboard_supports_dependency_injection():
    source = SERVICE.read_text(encoding="utf-8")
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
