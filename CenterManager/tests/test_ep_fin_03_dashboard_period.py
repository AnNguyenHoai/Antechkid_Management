from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.finance_dashboard_service import FinanceDashboardService


class FakeFinancePeriodService:
    def __init__(self, configured=True):
        self.configured = configured
        self.requested_dates = []

    def get_active_period(self, on_date):
        self.requested_dates.append(on_date)
        if not self.configured:
            return None
        return SimpleNamespace(
            effective_from=date(2026, 1, 1),
            duration_months=3,
        )

    @staticmethod
    def get_period_bounds(anchor_date, target_date, duration_months):
        assert anchor_date == date(2026, 1, 1)
        assert duration_months == 3
        if date(2026, 4, 1) <= target_date <= date(2026, 6, 30):
            return date(2026, 4, 1), date(2026, 6, 30)
        raise AssertionError(f"Unexpected target date: {target_date}")


class FakeIncomeService:
    def __init__(self):
        self.calls = []

    def list_incomes(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("finance_period_start") == date(2026, 4, 1):
            return ([
                SimpleNamespace(amount=100, payment_method="Cash"),
                SimpleNamespace(amount=200, payment_method="Bank Transfer"),
            ], 2)
        return ([SimpleNamespace(amount=25, payment_method="Cash")], 1)


class FakeExpenseService:
    def __init__(self):
        self.calls = []

    def list_expenses(self, **kwargs):
        self.calls.append(kwargs)
        if (
            kwargs.get("date_from") == date(2026, 4, 1)
            and kwargs.get("date_to") == date(2026, 6, 30)
        ):
            return ([SimpleNamespace(amount=40, payment_method="Cash"),
                     SimpleNamespace(amount=60, payment_method="Bank")], 2)
        return ([SimpleNamespace(amount=10, payment_method="Cash")], 1)


class FakeOutstandingService:
    def __init__(self):
        self.calls = []

    def get_outstanding_stats(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "total_outstanding": 500,
            "total_students_with_debt": 2,
            "total_unconfigured_tuition": 1,
        }


def test_dashboard_resolves_selected_month_to_canonical_finance_period():
    income = FakeIncomeService()
    expense = FakeExpenseService()
    outstanding = FakeOutstandingService()
    period_service = FakeFinancePeriodService()
    service = FinanceDashboardService(
        income,
        expense,
        outstanding,
        finance_period_service=period_service,
    )
    service._get_today_date = lambda: date(2026, 9, 18)

    data = service.get_dashboard_data(target_date=date(2026, 5, 1))

    assert data["period_configured"] is True
    assert data["period_start"] == date(2026, 4, 1)
    assert data["period_end"] == date(2026, 6, 30)
    assert data["period_label"] == "01/04/2026 - 30/06/2026"
    assert data["revenue_period"] == 300
    assert data["expense_period"] == 100
    assert data["net_cash_flow"] == 200
    assert data["revenue_month"] == data["revenue_period"]
    assert data["expense_month"] == data["expense_period"]
    assert data["revenue_by_method_month"] == data["revenue_by_method_period"]
    assert data["expense_by_method_month"] == data["expense_by_method_period"]
    assert period_service.requested_dates == [date(2026, 5, 1)]
    assert outstanding.calls == [{
        "period_start": date(2026, 4, 1),
        "on_date": date(2026, 5, 1),
    }]


def test_dashboard_income_uses_canonical_period_start_and_expense_uses_period_bounds():
    income = FakeIncomeService()
    expense = FakeExpenseService()
    service = FinanceDashboardService(
        income,
        expense,
        finance_period_service=FakeFinancePeriodService(),
    )
    service._get_today_date = lambda: date(2026, 9, 18)

    service.get_dashboard_data(target_date=date(2026, 5, 1))

    period_income_calls = [
        call for call in income.calls
        if call.get("finance_period_start") == date(2026, 4, 1)
    ]
    assert period_income_calls
    assert all(call["date_from"] == date(2026, 4, 1) for call in period_income_calls)
    assert all(call["date_to"] == date(2026, 6, 30) for call in period_income_calls)

    period_expense_calls = [
        call for call in expense.calls
        if call.get("date_from") == date(2026, 4, 1)
    ]
    assert period_expense_calls
    assert all(call["date_to"] == date(2026, 6, 30) for call in period_expense_calls)


def test_current_finance_period_caps_actuals_at_today():
    class CurrentPeriodService:
        @staticmethod
        def get_active_period(_target):
            return SimpleNamespace(effective_from=date(2026, 7, 1), duration_months=3)

        @staticmethod
        def get_period_bounds(_anchor, _target, _duration):
            return date(2026, 7, 1), date(2026, 9, 30)

    income = FakeIncomeService()
    expense = FakeExpenseService()
    service = FinanceDashboardService(
        income,
        expense,
        finance_period_service=CurrentPeriodService(),
    )
    service._get_today_date = lambda: date(2026, 9, 18)

    bounds = service._resolve_dashboard_period(date(2026, 8, 1))
    assert bounds == (date(2026, 7, 1), date(2026, 9, 30), date(2026, 9, 18))


def test_missing_finance_period_is_explicit_not_calendar_month_fallback():
    service = FinanceDashboardService(
        FakeIncomeService(),
        FakeExpenseService(),
        FakeOutstandingService(),
        finance_period_service=FakeFinancePeriodService(configured=False),
    )
    service._get_today_date = lambda: date(2026, 9, 18)

    data = service.get_dashboard_data(target_date=date(2026, 5, 1))

    assert data["period_configured"] is False
    assert data["period_start"] is None
    assert data["period_end"] is None
    assert data["revenue_period"] == 0
    assert data["expense_period"] == 0
    assert data["period_label"] == "Finance period not configured"


def test_dashboard_ui_has_month_year_selector_and_uses_selected_period_keys():
    source = Path(
        "src/centermanager/ui/finance_workspace/finance_dashboard_page.py"
    ).read_text(encoding="utf-8")

    assert "QComboBox" in source
    assert "self.month_combo" in source
    assert "self.year_combo" in source
    assert "target_date=self._selected_target_date()" in source
    assert 'data.get("revenue_period", 0)' in source
    assert 'data.get("expense_period", 0)' in source
    assert 'data.get("revenue_by_method_period", {})' in source
    assert 'data.get("expense_by_method_period", {})' in source
    assert "Selected Period" in source


def test_production_dashboard_adopts_finance_period_without_breaking_legacy_constructor():
    source = Path(
        "src/centermanager/services/finance_dashboard_service.py"
    ).read_text(encoding="utf-8")

    assert 'getattr(income_service, "_session_factory", None)' in source
    assert "FinancePeriodService(session_factory)" in source
    assert "finance_period_service=None" in source
