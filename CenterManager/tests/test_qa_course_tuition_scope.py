"""Regression gates: enrollment tuition is not reset at FinancePeriod boundaries.

All database/session fixtures are synthetic; tests do not touch the live DB.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from centermanager.dto.outstanding_dto import OutstandingDTO
from centermanager.services.outstanding_service import OutstandingService
from centermanager.ui.student_workspace.student_financial_widget import StudentFinancialWidget


class _Session:
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False


def _dto(enrollment_id, accrued, paid):
    return OutstandingDTO.create(
        student_id=1, student_name="Test", student_code="S1",
        class_id=11, class_name="Scratch",
        enrollment_id=enrollment_id,
        expected_tuition=Decimal(accrued),
        paid=Decimal(paid),
    )


def test_course_balance_is_not_restricted_to_enrollments_in_current_finance_period():
    """One contract spanning multiple months remains one financial identity."""
    service = OutstandingService(lambda: _Session())
    observations = []
    course_rows = [_dto(42, 800000, 500000), _dto(43, 200000, 350000)]
    service._report_period_for_request = lambda *a, **k: (
        (_ for _ in ()).throw(AssertionError("Course balance must not query FinancePeriod"))
    )

    def collect(*args, **kwargs):
        observations.append(kwargs)
        return course_rows

    service._collect_outstanding = collect
    summary = service.get_student_summary(
        student_id=1,
        period_start=date(2026, 11, 1),
        on_date=date(2026, 11, 3),
        view=OutstandingService.VIEW_COURSE_BALANCES,
    )
    assert observations[0]["resolved_period_start"] is None
    assert observations[0]["resolved_period_end"] is None
    assert observations[0]["view"] == OutstandingService.VIEW_COURSE_BALANCES
    assert len(summary.details) == 2
    assert summary.total_expected == Decimal("1000000")
    assert summary.total_paid == Decimal("850000")
    assert summary.total_outstanding == Decimal("150000")  # signed reconciliation only
    assert summary.debt_amount == Decimal("300000")  # never offset by other course
    assert summary.prepaid_amount == Decimal("150000")


def test_legacy_get_all_outstanding_does_not_raise_undefined_hide_flag():
    service = OutstandingService(lambda: _Session())
    forwarded = []
    def page(**kwargs):
        forwarded.append(kwargs)
        return [], 0, {}
    service.get_outstanding_page = page
    assert service.get_all_outstanding(hide_settled_inactive=True) == ([], 0)
    assert forwarded[0]["hide_settled_inactive"] is True


def test_student_finance_uses_course_view_and_all_time_tuition_receipts(qapp):
    captured = []
    permission = SimpleNamespace(has_permission=lambda name: name == "finance.view")
    income = SimpleNamespace(list_incomes=lambda **kwargs: (
        captured.append(kwargs) or ([], 0)
    ))
    outstanding = SimpleNamespace(get_student_summary=lambda *args, **kwargs: (
        captured.append(kwargs) or None
    ))
    widget = StudentFinancialWidget(income, None, None, permission, outstanding)
    widget._student_id = 1
    widget._load_outstanding_summary(date(2026, 11, 1), date(2026, 11, 3))
    widget._load_incomes(None, date(2026, 11, 3))
    assert captured[0]["view"] == OutstandingService.VIEW_COURSE_BALANCES
    assert captured[1]["finance_period_start"] is None
    assert captured[1]["date_from"] is None
    assert captured[1]["date_to"] == date(2026, 11, 3)
    assert captured[1]["income_type"] == "Tuition"


def test_open_receivable_stats_ignore_monthly_finance_period():
    service = OutstandingService(lambda: _Session())
    calls = []

    def page(**kwargs):
        calls.append(kwargs)
        return [], 0, {"total_outstanding": Decimal("300000"),
                       "total_students_with_debt": 1}

    service.get_outstanding_page = page
    stats = service.get_receivable_stats(on_date=date(2026, 11, 3))
    assert stats["total_outstanding"] == Decimal("300000")
    assert calls[0]["view"] == OutstandingService.VIEW_OPEN_RECEIVABLES
    assert calls[0]["as_of_date"] == date(2026, 11, 3)


def test_finance_dashboard_uses_receivables_not_selected_month_for_debt():
    from centermanager.services.finance_dashboard_service import FinanceDashboardService
    class DebtService:
        def get_receivable_stats(self, *, on_date=None):
            assert on_date == date(2026, 11, 3)
            return {"total_outstanding": Decimal("300000"),
                    "total_students_with_debt": 1}
        def get_outstanding_stats(self, **kwargs):
            raise AssertionError("Period-scoped debt is not collectible debt")

    dashboard = FinanceDashboardService.__new__(FinanceDashboardService)
    dashboard._outstanding_service = DebtService()
    assert dashboard._get_outstanding_stats(
        date(2026, 11, 1), date(2026, 11, 3)
    )["total_outstanding"] == Decimal("300000")


def test_finance_dashboard_reports_course_debt_without_accounting_period():
    from centermanager.services.finance_dashboard_service import FinanceDashboardService
    dashboard = FinanceDashboardService.__new__(FinanceDashboardService)
    day = date(2026, 11, 3)
    dashboard._get_today_date = lambda: day
    dashboard._resolve_dashboard_period = lambda *args, **kwargs: None
    dashboard.get_revenue_today = lambda: 0
    dashboard.get_expense_today = lambda: 0
    dashboard._get_outstanding_stats = lambda **kwargs: {
        "total_outstanding": Decimal("300000"),
        "total_students_with_debt": 1,
        "total_unconfigured_tuition": 0,
    }
    data = dashboard.get_dashboard_data(target_date=day, period_configured=False)
    assert data["period_configured"] is False
    assert data["total_outstanding"] == Decimal("300000")
    assert data["students_with_debt"] == 1
    assert data["revenue_period"] == 0
