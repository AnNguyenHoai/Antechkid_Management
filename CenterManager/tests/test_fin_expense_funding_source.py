# -*- coding: utf-8 -*-
"""FEAT-001 / BUG-002 / BUG-003: expense funding source and reimbursement.

PO decision 2026-11-04:
* company wallet (CASH/BANK) expenses are realized immediately;
* personal-account expenses are "CHƯA HOÀN TRẢ" and not company outflow;
* reimbursement chooses a company wallet and posts on the reimbursement date;
* legacy data is rewritten only outside CONFIRMED settlement periods.
"""
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.core.current_user import CurrentUserContext
from centermanager.database.base import Base
from centermanager.models import Expense
from centermanager.models.finance_period import FinancePeriod
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.services.expense_service import ExpenseService, ExpenseValidationError

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 20)
EDITOR = SimpleNamespace(
    id=None,
    username="finance-tester",
    full_name="Finance Tester",
    is_admin=False,
    is_active=True,
    role=SimpleNamespace(name="MANAGER"),
    permissions={"finance.view", "finance.expense.create", "finance.expense.update"},
)


@pytest.fixture
def expense_env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'expense_funding.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(FinancePeriod(id=1, duration_months=1, effective_from=date(2026, 1, 1)))
    set_clock(Clock(now_fn=lambda: datetime(2026, 10, 20, 9, 0), today_fn=lambda: TODAY))
    service = ExpenseService(factory, None, None)
    try:
        with CurrentUserContext(EDITOR):
            yield factory, service
    finally:
        reset_clock()
        engine.dispose()


def _create(service, method, *, day=date(2026, 10, 10), status=None, amount=100_000):
    kwargs = dict(
        category="Office Supply", description="Giấy in", amount=amount,
        payment_method=method, payment_date=day, paid_by="Nhân viên A",
    )
    if status is not None:
        kwargs["status"] = status
    return service.create_expense(**kwargs)


def _realized_by_wallet(service, date_from=date(2026, 10, 1), date_to=TODAY):
    rows = service.aggregate_by_payment_method(date_from=date_from, date_to=date_to)
    return {method: float(amount) for method, amount in rows}


@pytest.mark.parametrize("method", ["CASH", "BANK"])
def test_company_wallet_expense_is_realized_immediately(expense_env, method):
    _factory, service = expense_env
    expense = _create(service, method)

    assert expense.funding_source == Expense.FUNDING_COMPANY
    assert expense.status == "Completed"
    assert expense.payment_method == method
    assert expense.finance_period_id == 1
    assert _realized_by_wallet(service) == {method: 100_000.0}


def test_company_wallet_expense_cannot_be_planned_pending(expense_env):
    _factory, service = expense_env
    with pytest.raises(ExpenseValidationError):
        _create(service, "BANK", status="Pending")


def test_personal_expense_is_not_company_outflow_until_reimbursed(expense_env):
    _factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 10, 5))

    assert expense.funding_source == Expense.FUNDING_PERSONAL
    assert expense.status == "Pending"
    assert expense.payment_method == Expense.PERSONAL_PAYMENT_METHOD
    assert expense.incurred_date == date(2026, 10, 5)
    assert _realized_by_wallet(service) == {}


def test_personal_legacy_label_is_classified_as_personal(expense_env):
    _factory, service = expense_env
    expense = _create(service, "TÀI KHOẢN CÁ NHÂN")
    assert expense.funding_source == Expense.FUNDING_PERSONAL
    assert expense.status == "Pending"


def test_personal_expense_cannot_be_created_as_reimbursed(expense_env):
    _factory, service = expense_env
    with pytest.raises(ExpenseValidationError):
        _create(service, "PERSONAL", status="Completed")


def test_reimbursement_posts_on_reimbursement_date_from_chosen_wallet(expense_env):
    _factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 9, 28))

    reimbursed = service.reimburse_expense(expense.id, wallet="BANK", reimbursement_date=date(2026, 10, 15))

    assert reimbursed.status == "Completed"
    assert reimbursed.funding_source == Expense.FUNDING_PERSONAL
    assert reimbursed.payment_method == "BANK"
    assert reimbursed.payment_date == date(2026, 10, 15)
    assert reimbursed.incurred_date == date(2026, 9, 28)
    assert reimbursed.finance_period_id == 1
    # Counted in October (reimbursement), not September (original spend).
    assert _realized_by_wallet(service) == {"BANK": 100_000.0}
    assert _realized_by_wallet(service, date(2026, 9, 1), date(2026, 9, 30)) == {}


def test_reimbursement_cannot_happen_twice(expense_env):
    _factory, service = expense_env
    expense = _create(service, "PERSONAL")
    service.reimburse_expense(expense.id, wallet="CASH", reimbursement_date=TODAY)
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="CASH", reimbursement_date=TODAY)


def test_reimbursement_requires_company_wallet_and_valid_date(expense_env):
    _factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 10, 10))
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="PERSONAL", reimbursement_date=TODAY)
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="BANK", reimbursement_date=date(2026, 10, 9))
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="BANK", reimbursement_date=date(2026, 10, 21))


def test_company_expense_is_not_reimbursable(expense_env):
    _factory, service = expense_env
    expense = _create(service, "CASH")
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="BANK", reimbursement_date=TODAY)


def test_reimbursement_into_confirmed_period_is_rejected(expense_env):
    factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 9, 10))
    with factory.begin() as session:
        session.add(FinancialSettlement(
            finance_period_start=date(2026, 9, 1),
            finance_period_end=date(2026, 9, 30),
            status=FinancialSettlement.STATUS_CONFIRMED,
        ))
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, wallet="CASH", reimbursement_date=date(2026, 9, 20))
    # Reimbursing in the next open period is allowed.
    service.reimburse_expense(expense.id, wallet="CASH", reimbursement_date=date(2026, 10, 2))


def test_pending_personal_expense_cannot_be_completed_by_edit(expense_env):
    _factory, service = expense_env
    expense = _create(service, "PERSONAL")
    with pytest.raises(ExpenseValidationError):
        service.update_expense(expense.id, status="Completed")
    with pytest.raises(ExpenseValidationError):
        service.update_expense(expense.id, payment_method="CASH")
    updated = service.update_expense(expense.id, amount=150_000, payment_date=date(2026, 10, 12))
    assert updated.status == "Pending"
    assert updated.incurred_date == date(2026, 10, 12)


def test_company_expense_cannot_switch_to_personal_or_pending(expense_env):
    _factory, service = expense_env
    expense = _create(service, "BANK")
    with pytest.raises(ExpenseValidationError):
        service.update_expense(expense.id, payment_method="PERSONAL")
    with pytest.raises(ExpenseValidationError):
        service.update_expense(expense.id, status="Pending")
    assert service.update_expense(expense.id, payment_method="CASH").payment_method == "CASH"


def test_list_cash_flow_total_matches_dashboard_definition(expense_env):
    """BUG-003: realized sum used by the list equals the Dashboard aggregate."""
    _factory, service = expense_env
    _create(service, "CASH", amount=200_000)
    _create(service, "PERSONAL", amount=50_000)
    reimbursed = _create(service, "PERSONAL", amount=70_000)
    service.reimburse_expense(reimbursed.id, wallet="BANK", reimbursement_date=TODAY)

    realized = service.sum_expenses(
        date_from=date(2026, 10, 1), date_to=date(2026, 10, 31),
        finance_period_start=date(2026, 10, 1), realized_only=True,
    )
    everything = service.sum_expenses(
        date_from=date(2026, 10, 1), date_to=date(2026, 10, 31),
        finance_period_start=date(2026, 10, 1),
    )
    assert float(realized) == sum(_realized_by_wallet(service).values()) == 270_000.0
    assert float(everything) - float(realized) == 50_000.0


def test_migration_rewrites_only_open_periods_and_is_registered():
    migration = (ROOT / "migrations" / "versions" / "1e10a043_expense_funding_source.py").read_text(encoding="utf-8")
    verifier = (ROOT / "src" / "centermanager" / "database" / "migration.py").read_text(encoding="utf-8")
    assert 'down_revision = "1e10a042"' in migration
    assert "s.status = 'CONFIRMED'" in migration
    assert '"expenses": {"funding_source", "incurred_date"}' in verifier


def test_migration_normalizes_legacy_rows_outside_confirmed_periods(migration_db_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from centermanager.database.engine import create_engine_for_path

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")
    command.upgrade(cfg, "1e10a042")

    engine = create_engine_for_path(migration_db_path)
    rows = [
        (1, "TÀI KHOẢN CÁ NHÂN", "CHƯA HOÀN TRẢ", "2026-09-05"),
        (2, "TÀI KHOẢN CÁ NHÂN", "ĐÃ HOÀN TRẢ", "2026-09-06"),
        (3, "TÀI KHOẢN CÔNG TY", "CHƯA HOÀN TRẢ", "2026-09-07"),
        (4, "Cash", "Pending", "2026-09-08"),
        (5, "TÀI KHOẢN CÔNG TY", "CHƯA HOÀN TRẢ", "2026-08-15"),
    ]
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO finance_periods (id, duration_months, status, effective_from) "
            "VALUES (7, 1, 'ACTIVE', '2026-01-01')"
        ))
        connection.execute(text(
            "INSERT INTO financial_settlements (finance_period_start, finance_period_end, status) "
            "VALUES ('2026-08-01', '2026-08-31', 'CONFIRMED')"
        ))
        for row_id, method, status, day in rows:
            connection.execute(text(
                "INSERT INTO expenses (id, category, amount, payment_method, status, payment_date) "
                "VALUES (:id, 'Other', 100, :method, :status, :day)"
            ), {"id": row_id, "method": method, "status": status, "day": day})
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine_for_path(migration_db_path)
    with engine.connect() as connection:
        result = {
            row.id: (row.payment_method, row.status, row.funding_source, row.finance_period_id)
            for row in connection.execute(text(
                "SELECT id, payment_method, status, funding_source, finance_period_id FROM expenses"
            ))
        }
    engine.dispose()

    assert result[1] == ("PERSONAL", "Pending", "PERSONAL", None)
    assert result[2] == ("CASH", "Completed", "PERSONAL", 7)
    assert result[3] == ("BANK", "Completed", "COMPANY", 7)
    # Old planned company expense: left for manual review.
    assert result[4] == ("Cash", "Pending", None, None)
    # Inside a CONFIRMED settlement period: untouched.
    assert result[5] == ("TÀI KHOẢN CÔNG TY", "CHƯA HOÀN TRẢ", None, None)


def test_october_personal_advance_repaid_in_november_is_november_cashflow(expense_env):
    """Original spend stays October; company wallet posts only on Nov reimbursement."""
    factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 10, 10), amount=200_000)
    with factory.begin() as session:
        session.add(FinancialSettlement(
            finance_period_start=date(2026, 10, 1),
            finance_period_end=date(2026, 10, 31),
            status=FinancialSettlement.STATUS_CONFIRMED,
        ))
    set_clock(Clock(now_fn=lambda: datetime(2026, 11, 9, 9, 0),
                    today_fn=lambda: date(2026, 11, 9)))
    paid = service.reimburse_expense(
        expense.id, wallet="BANK", reimbursement_date=date(2026, 11, 5)
    )
    assert paid.incurred_date == date(2026, 10, 10)
    assert paid.payment_date == date(2026, 11, 5)
    assert paid.status == "Completed"
    assert paid.payment_method == "BANK"
    assert paid.funding_source == Expense.FUNDING_PERSONAL
    assert float(service.sum_expenses(
        date_from=date(2026, 10, 1), date_to=date(2026, 10, 31),
        realized_only=True
    )) == 0
    assert float(service.sum_expenses(
        date_from=date(2026, 11, 1), date_to=date(2026, 11, 30),
        realized_only=True
    )) == 200_000
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(
            expense.id, wallet="CASH", reimbursement_date=date(2026, 11, 6)
        )
    assert service.get_expense(expense.id).payment_date == date(2026, 11, 5)


def test_november_reimbursement_cannot_post_into_closed_november(expense_env):
    factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 10, 10))
    with factory.begin() as session:
        session.add(FinancialSettlement(
            finance_period_start=date(2026, 11, 1),
            finance_period_end=date(2026, 11, 30),
            status=FinancialSettlement.STATUS_CONFIRMED,
        ))
    set_clock(Clock(now_fn=lambda: datetime(2026, 11, 9, 9, 0),
                    today_fn=lambda: date(2026, 11, 9)))
    with pytest.raises(ExpenseValidationError):
        service.reimburse_expense(expense.id, "BANK", date(2026, 11, 5))
    still_pending = service.get_expense(expense.id)
    assert still_pending.status == "Pending"
    assert still_pending.incurred_date == date(2026, 10, 10)


def test_expense_repayment_ui_exposes_direct_button_and_both_dates():
    root = ROOT / "src" / "centermanager" / "ui" / "finance_workspace"
    listing = (root / "expense_list_page.py").read_text(encoding="utf-8")
    detail = (root / "expense_detail_dialog.py").read_text(encoding="utf-8")
    assert 'SecondaryButton("Hoàn trả khoản đã chọn")' in listing
    assert 'self.data_table.selection_changed.connect(self._on_expense_selection_changed)' in listing
    assert 'self.reimburse_btn.clicked.connect(self._reimburse_selected)' in listing
    assert '"label": "Ngày phát sinh"' in listing
    assert '"label": "Ngày thanh toán"' in listing
    assert 'domain_allowed=True' in listing
    assert 'form.addRow("Ngày phát sinh:", self.incurred_date_label)' in detail
    assert 'form.addRow("Ngày thanh toán:", self.date_label)' in detail
