from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.finance_dashboard_service import FinanceDashboardService


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "finance_dashboard_service.py"
PAGE = ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "finance_dashboard_page.py"
SHELL = ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "finance_workspace_shell.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dashboard_uses_workspace_shared_finance_period_contract():
    source = _source(PAGE)
    assert "self._period_start = period_start" in source
    assert "self._period_end = period_end" in source
    assert "self._period_configured = period_configured" in source
    assert "period_start=self._period_start" in source
    assert "period_end=self._period_end" in source
    assert "period_configured=self._period_configured" in source
    assert "month_combo" not in source
    assert "year_combo" not in source


def test_dashboard_explicit_shared_period_drives_all_live_aggregations():
    period_start = date(2026, 8, 1)
    period_end = date(2026, 8, 31)
    target_date = date(2026, 8, 1)
    income_calls = []
    expense_calls = []
    outstanding_calls = []

    class IncomeService:
        def list_incomes(self, **kwargs):
            income_calls.append(kwargs)
            if kwargs.get("date_from") == period_start:
                return [
                    SimpleNamespace(amount=100, payment_method="Cash"),
                    SimpleNamespace(amount=300, payment_method="Bank Transfer"),
                ], 2
            return [], 0

    class ExpenseService:
        def list_expenses(self, **kwargs):
            expense_calls.append(kwargs)
            if kwargs.get("date_from") == period_start:
                return [
                    SimpleNamespace(amount=40, payment_method="Cash"),
                    SimpleNamespace(amount=80, payment_method="Bank"),
                ], 2
            return [], 0

    class OutstandingService:
        def get_outstanding_stats(self, **kwargs):
            outstanding_calls.append(kwargs)
            return {
                "total_outstanding": 500,
                "total_students_with_debt": 2,
                "total_unconfigured_tuition": 1,
            }

    service = FinanceDashboardService(
        IncomeService(), ExpenseService(), OutstandingService()
    )
    service._get_today_date = lambda: date(2026, 9, 19)

    data = service.get_dashboard_data(
        target_date=target_date,
        period_start=period_start,
        period_end=period_end,
        period_configured=True,
    )

    assert data["period_start"] == period_start
    assert data["period_end"] == period_end
    assert data["revenue_period"] == 400
    assert data["expense_period"] == 120
    assert data["net_cash_flow"] == 280
    assert data["total_outstanding"] == 500

    assert any(
        call.get("date_from") == period_start
        and call.get("date_to") == period_end
        and call.get("finance_period_start") == period_start
        for call in income_calls
    )
    assert any(
        call.get("date_from") == period_start
        and call.get("date_to") == period_end
        for call in expense_calls
    )
    assert outstanding_calls == [
        {"period_start": period_start, "on_date": target_date}
    ]


def test_dashboard_cash_vs_bank_is_service_owned_and_live():
    result = FinanceDashboardService._build_cash_vs_bank(
        {"Cash": 150, "Bank": 500, "Other": 20},
        {"Cash": 40, "Bank": 120, "Other": 10},
    )
    assert result == {
        "Cash": {"income": 150.0, "expense": 40.0, "net": 110.0},
        "Bank": {"income": 500.0, "expense": 120.0, "net": 380.0},
    }

    service_source = _source(SERVICE)
    page_source = _source(PAGE)
    assert '"cash_vs_bank": self._build_cash_vs_bank(' in service_source
    assert "self.cash_vs_bank_chart" in page_source
    assert 'cash_vs_bank = data.get("cash_vs_bank", {})' in page_source


def test_dashboard_has_workspace_drilldowns_without_money_mutations():
    page_source = _source(PAGE)
    shell_source = _source(SHELL)

    assert "drilldown_requested = Signal(str)" in page_source
    assert 'self.drilldown_requested.emit(target)' in page_source
    assert "self.dashboard_page.drilldown_requested.connect(self.navigate_to)" in shell_source

    for mutation in (
        "create_income(",
        "update_income(",
        "delete_income(",
        "void_income(",
        "create_expense(",
        "update_expense(",
        "delete_expense(",
    ):
        assert mutation not in page_source


def test_dashboard_refreshes_through_existing_finance_data_changed_event():
    shell_source = _source(SHELL)
    assert "self._event_bus.register(FinanceDataChanged, self._on_finance_data_changed)" in shell_source
    assert "def _on_finance_data_changed" in shell_source
    assert "self.dashboard_page," in shell_source
    assert "self._refresh_pages([" in shell_source


def test_dashboard_service_stays_read_only_and_settlement_independent():
    source = _source(SERVICE)
    lowered = source.lower()
    assert "settlement" not in lowered
    for mutation in (
        "create_income(",
        "update_income(",
        "delete_income(",
        "void_income(",
        "create_expense(",
        "update_expense(",
        "delete_expense(",
    ):
        assert mutation not in source


def test_unconfigured_shared_period_returns_zero_period_kpis():
    class IncomeService:
        def list_incomes(self, **kwargs):
            return [], 0

    class ExpenseService:
        def list_expenses(self, **kwargs):
            return [], 0

    class OutstandingService:
        def get_outstanding_stats(self, **kwargs):
            raise AssertionError("Outstanding must not be loaded without a period")

    service = FinanceDashboardService(
        IncomeService(), ExpenseService(), OutstandingService()
    )
    data = service.get_dashboard_data(
        target_date=date(2026, 9, 1),
        period_start=None,
        period_end=None,
        period_configured=False,
    )

    assert data["period_configured"] is False
    assert data["revenue_period"] == 0
    assert data["expense_period"] == 0
    assert data["net_cash_flow"] == 0
    assert data["total_outstanding"] == 0
