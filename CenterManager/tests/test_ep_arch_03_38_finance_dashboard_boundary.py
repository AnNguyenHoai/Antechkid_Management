"""EP-ARCH-03.38 — FinanceDashboardService boundary contract."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "finance_dashboard_service.py"
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_finance_dashboard_is_application_aggregation_only():
    source = SERVICE.read_text(encoding="utf-8")

    assert "RepositoryProvider" not in source
    assert "create_default_repository_provider" not in source
    assert "centermanager.repositories." not in source
    assert "session.query(" not in source
    assert "session.execute(" not in source
    assert "session.add(" not in source
    assert "session.delete(" not in source
    assert "session.refresh(" not in source
    assert "session.get(" not in source

    # Dashboard aggregation is intentionally composed from provider-backed services.
    assert "IncomeService" in source
    assert "ExpenseService" in source
    assert "outstanding_service" in source


def test_finance_dashboard_is_not_left_in_database_backed_legacy_backlog():
    source = INVENTORY.read_text(encoding="utf-8")
    row_start = source.index("`finance_dashboard_service.py`")
    row = source[row_start:source.index("\n", row_start)]
    assert "| NON_REPOSITORY |" in row, row
    assert "EP-ARCH-03.38 Finance Dashboard boundary" in source
