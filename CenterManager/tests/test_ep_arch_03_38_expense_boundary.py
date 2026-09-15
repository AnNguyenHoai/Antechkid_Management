"""EP-ARCH-03.38A — ExpenseService repository-boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "src" / "centermanager" / "services"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_expense_services_use_repository_provider_boundary():
    expense = (SERVICES / "expense_service.py").read_text(encoding="utf-8")
    timeline = (SERVICES / "expense_timeline_service.py").read_text(encoding="utf-8")

    for source in (expense, timeline):
        assert "RepositoryProvider" in source
        assert "centermanager.repositories.expense_repository" not in source
        assert "centermanager.repositories.expense_timeline_repository" not in source
        assert "session.query(" not in source
        assert "session.add(" not in source
        assert "session.delete(" not in source
        assert "session.refresh(" not in source
        assert "repo.refresh(" in source


def test_expense_services_are_promoted_to_pass():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in ("expense_service.py", "expense_timeline_service.py"):
        row_start = source.index(f"`{service_name}`")
        row = source[row_start:source.index("\n", row_start)]
        assert "| PASS |" in row, row
    assert "EP-ARCH-03.38 Expense repository boundary" in source
