"""EP-ARCH-03.30 - OutstandingService repository boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"


def test_outstanding_service_uses_repository_provider():
    source = SERVICE.read_text(encoding="utf-8")
    assert "from centermanager.repositories.provider import" in source
    for concrete in (
        "StudentRepository",
        "ClassRepository",
        "EnrollmentRepository",
        "IncomeRepository",
    ):
        assert concrete not in source
    assert "session.query(" not in source
    assert "session.get(" not in source


def test_outstanding_service_routes_reads_through_provider():
    source = SERVICE.read_text(encoding="utf-8")
    for factory in ("students", "classes", "enrollments", "incomes"):
        assert f"self._repository_provider.{factory}(session)" in source


def test_outstanding_service_keeps_provider_injection():
    source = SERVICE.read_text(encoding="utf-8")
    assert "repository_provider: Optional[RepositoryProvider] = None" in source
    assert "self._repository_provider = repository_provider or create_default_repository_provider()" in source
