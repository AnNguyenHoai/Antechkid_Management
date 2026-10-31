"""F-25 / NEW-01 complete Dashboard totals and canonical Wallet mapping."""
from datetime import date, datetime
from decimal import Decimal
from time import perf_counter
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, insert
from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.models import Class, Enrollment, Expense, Income, Student
from centermanager.services.expense_service import ExpenseService
from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.services.financial_settlement_service import FinancialSettlementService
from centermanager.services.income_service import IncomeService
from centermanager.services.permission_service import PermissionDeniedError
from centermanager.services.wallet_service import WalletService


START = date(2026, 10, 1)
END = date(2026, 10, 30)
VIEWER = SimpleNamespace(role=SimpleNamespace(name="MANAGER"), permissions={"finance.view"})


@pytest.fixture
def finance_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'finance_dashboard.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    income = IncomeService(factory, None, None, None, None)
    expense = ExpenseService(factory, None, None)
    yield factory, engine, FinanceDashboardService(income, expense), WalletService(factory), FinancialSettlementService(factory)
    engine.dispose()


@pytest.mark.parametrize("kind", ["income", "expense"])
def test_dashboard_total_includes_transactions_beyond_first_page(finance_db, kind):
    """One grouped query includes all 10,001 realized rows without ORM materialization."""
    factory, engine, dashboard, wallet, settlement = finance_db
    values = [dict(amount=1, payment_method="CASH", payment_date=START, **(
        dict(income_type="Other", status="ACTIVE", finance_period_start=START)
        if kind == "income" else dict(category="Operations", status="Completed")
    )) for _ in range(10001)]
    with factory.begin() as session:
        session.execute(insert(Income if kind == "income" else Expense), values)
    statements = []

    def record(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        with CurrentUserContext(VIEWER):
            legacy_start = perf_counter()
            legacy_rows, legacy_count = (
                dashboard._income_service.list_incomes(
                    date_from=START, date_to=END, finance_period_start=START,
                    page=1, per_page=10000,
                ) if kind == "income" else dashboard._expense_service.list_expenses(
                    date_from=START, date_to=END, finance_period_start=START,
                    realized_only=True, page=1, per_page=10000,
                )
            )
            legacy_ms = (perf_counter() - legacy_start) * 1000
            legacy_queries = len(statements)
            statements.clear()
            started = perf_counter()
            result = (dashboard.get_revenue_by_payment_method(START, END, START)
                      if kind == "income" else dashboard.get_expense_by_payment_method(START, END, START))
            elapsed_ms = (perf_counter() - started) * 1000
            dashboard._get_today_date = lambda: START
            today_total = dashboard.get_revenue_today() if kind == "income" else dashboard.get_expense_today()
            month_total = dashboard.get_revenue_this_month() if kind == "income" else dashboard.get_expense_this_month()
            summary = wallet.get_period_summary(period_start=START, period_end=END)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert result == {"Cash": 10001.0, "Bank": 0.0, "Other": 0.0}
    assert legacy_count == 10001 and len(legacy_rows) == 10000
    assert sum(row.amount for row in legacy_rows) == 10000  # Before: silent first-page truncation.
    assert today_total == month_total == 10001.0
    assert (summary.cash.realized_income if kind == "income" else summary.cash.realized_expense) == Decimal("10001.00")
    assert len(statements) == 5  # Three Dashboard GROUP BY reads; Wallet: two GROUP BY reads.
    assert all("GROUP BY" in sql.upper() and "LIMIT" not in sql.upper() for sql in statements)
    print(
        f"F-25 {kind}: old list {legacy_ms:.2f} ms / {legacy_queries} SQL / 10000 of 10001; "
        f"new aggregate {elapsed_ms:.2f} ms / 1 SQL / 10001 of 10001"
    )
    with factory() as session:
        activity = settlement._aggregate_activity(session, START, END)
    assert activity[f"{kind}_cash"] == Decimal("10001.00")


@pytest.mark.parametrize("kind", ["income", "expense"])
def test_unknown_wallet_alias_fails_dashboard_wallet_and_settlement(finance_db, kind):
    factory, _, dashboard, wallet, settlement = finance_db
    with factory.begin() as session:
        if kind == "income":
            session.add(Income(amount=100, income_type="Other", payment_method="UNKNOWN_LEGACY",
                               payment_date=START, finance_period_start=START, status="ACTIVE"))
        else:
            session.add(Expense(amount=100, category="Operations", payment_method="UNKNOWN_LEGACY",
                                payment_date=START, status="Completed"))
    with CurrentUserContext(VIEWER):
        with pytest.raises(ValueError, match="unknown wallet alias"):
            if kind == "income":
                dashboard.get_revenue_by_payment_method(START, END, START)
            else:
                dashboard.get_expense_by_payment_method(START, END, START)
        with pytest.raises(ValueError, match="unknown wallet alias"):
            wallet.get_period_summary(period_start=START, period_end=END)
    with factory() as session, pytest.raises(ValueError, match="unknown wallet alias"):
        settlement._aggregate_activity(session, START, END)


def test_period_realized_and_archived_old_debt_match_wallet(finance_db):
    factory, _, dashboard, wallet, _ = finance_db
    with factory.begin() as session:
        student = Student(student_code="S-F25", full_name="Synthetic Archived", status="ARCHIVED")
        class_ = Class(name="Historical Class", status="ARCHIVED", deleted_at=datetime(2026, 9, 30))
        session.add_all([student, class_]); session.flush()
        enrollment = Enrollment(student_id=student.id, class_id=class_.id,
                                status="WITHDRAWN", start_date=date(2026, 8, 1), end_date=date(2026, 9, 30))
        session.add(enrollment); session.flush()
        session.add_all([
            Income(student_id=student.id, class_id=class_.id, enrollment_id=enrollment.id,
                   amount=875000, income_type="Tuition", payment_method="CASH",
                   payment_date=START, finance_period_start=START, status="ACTIVE"),
            Income(amount=50, income_type="Other", payment_method="BANK", payment_date=START,
                   finance_period_start=START, status="VOIDED"),
            Income(amount=40, income_type="Other", payment_method="BANK", payment_date=START,
                   finance_period_start=START, status="ACTIVE", deleted_at=datetime(2026, 10, 2)),
            Income(amount=30, income_type="Other", payment_method="BANK", payment_date=START,
                   finance_period_start=date(2026, 9, 1), status="ACTIVE"),
            Expense(amount=15, category="Operations", payment_method="BANK", payment_date=START, status="Pending"),
            Expense(amount=25, category="Operations", payment_method="BANK", payment_date=START, status="Paid"),
            Expense(amount=20, category="Operations", payment_method="BANK", payment_date=START,
                    status="Completed", deleted_at=datetime(2026, 10, 2)),
        ])
    with CurrentUserContext(VIEWER):
        revenue = dashboard.get_revenue_by_payment_method(START, END, START)
        expense = dashboard.get_expense_by_payment_method(START, END, START)
        summary = wallet.get_period_summary(period_start=START, period_end=END)
    assert revenue == {"Cash": 875000.0, "Bank": 0.0, "Other": 0.0}
    assert expense == {"Cash": 0.0, "Bank": 25.0, "Other": 0.0}
    assert summary.cash.realized_income == Decimal("875000.00")
    assert summary.bank.realized_expense == Decimal("25.00")


def test_aggregate_service_methods_require_finance_view(finance_db):
    _, _, dashboard, _, _ = finance_db
    with CurrentUserContext(None):
        with pytest.raises(PermissionDeniedError):
            dashboard.get_revenue_by_payment_method(START, END, START)
        with pytest.raises(PermissionDeniedError):
            dashboard.get_expense_by_payment_method(START, END, START)
