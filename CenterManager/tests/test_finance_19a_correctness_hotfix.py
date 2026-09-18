from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.services.finance_dashboard_service import FinanceDashboardService


def _read(relative_path: str) -> str:
    return Path(relative_path).read_text(encoding="utf-8")


def test_expense_create_requires_canonical_create_capability():
    source = _read("src/centermanager/services/expense_service.py")
    marker = '@require_permission("finance.expense.create")\n    def create_expense'
    assert marker in source


def test_dashboard_snapshot_uses_month_start_not_today_for_month_kpis():
    calls = []

    class IncomeService:
        def list_incomes(self, **kwargs):
            calls.append(("income", kwargs["date_from"], kwargs["date_to"]))
            return [SimpleNamespace(amount=100, payment_method="Cash")], 1

    class ExpenseService:
        def list_expenses(self, **kwargs):
            calls.append(("expense", kwargs["date_from"], kwargs["date_to"]))
            return [SimpleNamespace(amount=40, payment_method="Cash")], 1

    class OutstandingService:
        def get_outstanding_stats(self):
            return {
                "total_outstanding": 0,
                "total_students_with_debt": 0,
                "total_unconfigured_tuition": 0,
            }

    service = FinanceDashboardService(IncomeService(), ExpenseService(), OutstandingService())
    service._get_today_date = lambda: date(2026, 9, 18)
    snapshot = service.get_dashboard_snapshot()

    assert calls == [
        ("income", date(2026, 9, 1), date(2026, 9, 18)),
        ("expense", date(2026, 9, 1), date(2026, 9, 18)),
    ]
    assert snapshot.cash_in_month == 100
    assert snapshot.cash_out_month == 40
    assert snapshot.net_cash_month == 60


def test_outstanding_stats_exposes_unconfigured_tuition_count():
    source = _read("src/centermanager/services/outstanding_service.py")
    assert '"total_unconfigured_tuition": total_unconfigured_tuition' in source
    assert "sum(1 for dto in all_dtos if not dto.tuition_configured)" in source


def test_income_search_preserves_nullable_student_and_class_records():
    source = _read("src/centermanager/repositories/income_repository.py")
    assert "query.outerjoin(Income.student)" in source
    assert ".outerjoin(Income.class_)" in source
    assert "Income.income_type.ilike(search)" in source
    assert "Income.received_by.ilike(search)" in source
    assert "query.join(Income.student).join(Income.class_)" not in source
