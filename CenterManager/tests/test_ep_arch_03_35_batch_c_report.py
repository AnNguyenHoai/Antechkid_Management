"""EP-ARCH-03.35 Batch C — ReportService boundary contract."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE = PROJECT_ROOT / "src" / "centermanager" / "services" / "report_service.py"


def test_report_service_is_provider_backed():
    source = SERVICE.read_text(encoding="utf-8")
    assert "from centermanager.repositories.provider import RepositoryProvider" in source
    assert "self._repository_provider.reports(session)" in source


def test_report_service_does_not_refresh_entities_directly():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.refresh(" not in source
    assert "repo.refresh(" in source


def test_report_service_keeps_transaction_completion_in_service():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.commit()" in source
