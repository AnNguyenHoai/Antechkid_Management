from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.finance_dashboard_service import FinanceDashboardService


class FakeIncomeService:
    def list_incomes(self, **kwargs):
        return ([
            SimpleNamespace(amount=100, payment_method="Cash"),
            SimpleNamespace(amount=200, payment_method="Bank Transfer"),
            SimpleNamespace(amount=50, payment_method="Other"),
        ], 3)


class FakeExpenseService:
    def list_expenses(self, **kwargs):
        return ([
            SimpleNamespace(amount=30, payment_method="Cash"),
            SimpleNamespace(amount=70, payment_method="Bank"),
        ], 2)


class FakeOutstandingService:
    def get_outstanding_stats(self):
        return {
            "total_outstanding": 500,
            "total_students_with_debt": 2,
            "total_unconfigured_tuition": 1,
        }


def test_dashboard_snapshot_has_finance_health_metrics():
    service = FinanceDashboardService(
        FakeIncomeService(), FakeExpenseService(), FakeOutstandingService()
    )
    snapshot = service.get_dashboard_snapshot()
    assert snapshot.cash_in_month == 100
    assert snapshot.bank_in_month == 200
    assert snapshot.cash_out_month == 30
    assert snapshot.bank_out_month == 70
    assert snapshot.net_cash_month == 70
    assert snapshot.net_bank_month == 130
    assert snapshot.total_outstanding == 500
    assert snapshot.students_with_debt == 2
    assert snapshot.unconfigured_tuition_count == 1


def test_dashboard_payment_methods_are_normalized():
    service = FinanceDashboardService(FakeIncomeService(), FakeExpenseService())
    data = service.get_revenue_by_payment_method(date.today(), date.today())
    assert data["Cash"] == 100
    assert data["Bank"] == 200
    assert data["Other"] == 50


def test_dashboard_ui_consumes_outstanding_metrics():
    source = Path("src/centermanager/ui/finance_workspace/finance_dashboard_page.py").read_text(encoding="utf-8")
    assert 'total_outstanding = data.get("total_outstanding", 0)' in source
    assert 'net_cash_month' in source
    assert 'net_bank_month' in source


def test_app_injects_outstanding_source_of_truth():
    source = Path("src/centermanager/app.py").read_text(encoding="utf-8")
    assert "FinanceDashboardService(" in source
    assert "outstanding_service" in source
