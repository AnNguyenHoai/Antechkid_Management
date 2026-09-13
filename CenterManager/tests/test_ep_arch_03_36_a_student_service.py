"""EP-ARCH-03.36-A — StudentService repository boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "student_service.py"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_student_service_uses_repository_provider_and_repository_owned_persistence():
    source = SERVICE.read_text(encoding="utf-8")
    assert "RepositoryProvider" in source
    assert "self._repository_provider.students(session)" in source
    assert "session.query(" not in source
    assert "session.execute(" not in source
    assert "session.get(" not in source
    assert "session.add(" not in source
    assert "session.delete(" not in source
    assert "session.refresh(" not in source
    assert "repo.refresh(" in source


def test_student_service_inventory_is_explicitly_promoted():
    source = INVENTORY.read_text(encoding="utf-8")
    row_start = source.index("`student_service.py`")
    row = source[row_start:source.index("\n", row_start)]
    assert "| PASS |" in row
    assert "**StudentService**" in source
    assert "RepositoryProvider.students(...)" in source


def test_student_service_keeps_transaction_and_application_orchestration():
    source = SERVICE.read_text(encoding="utf-8")
    assert "session.commit()" in source
    assert "self._timeline_service" in source
    assert "self._event_bus" in source
    assert "self._report_policy" in source
