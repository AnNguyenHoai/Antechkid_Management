from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.models.expense import Expense
from centermanager.models.finance_period import FinancePeriod
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.models.income import Income
from centermanager.services.financial_settlement_service import FinancialSettlementService


def _service_with_period(test_db_path, monkeypatch):
    engine = create_engine_for_path(test_db_path)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(
        "centermanager.services.financial_settlement_service.get_current_user",
        lambda: SimpleNamespace(is_admin=True),
    )
    with factory() as session:
        session.add(
            FinancePeriod(
                duration_months=3,
                status=FinancePeriod.STATUS_ACTIVE,
                effective_from=date(2026, 1, 1),
                effective_to=None,
            )
        )
        session.commit()
    return engine, factory, FinancialSettlementService(factory)


def _seed_activity(factory):
    with factory() as session:
        session.add_all(
            [
                Income(
                    amount=100.10,
                    income_type="Tuition",
                    payment_method="Cash",
                    payment_date=date(2026, 4, 5),
                    finance_period_start=date(2026, 4, 1),
                ),
                Income(
                    amount=200.20,
                    income_type="Tuition",
                    payment_method="Bank Transfer",
                    payment_date=date(2026, 5, 6),
                    finance_period_start=date(2026, 4, 1),
                ),
                Income(
                    amount=999.0,
                    income_type="Other",
                    payment_method="Cash",
                    payment_date=date(2026, 3, 31),
                    finance_period_start=date(2026, 1, 1),
                ),
                Expense(
                    category="Material",
                    amount=40.0,
                    payment_method="Cash",
                    status="Paid",
                    payment_date=date(2026, 4, 8),
                ),
                Expense(
                    category="Rent",
                    amount=50.0,
                    payment_method="Bank Transfer",
                    status="Paid",
                    payment_date=date(2026, 6, 1),
                ),
            ]
        )
        session.commit()


def test_settlement_preview_resolves_canonical_period_and_splits_cash_bank(test_db_path, monkeypatch):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        _seed_activity(factory)
        preview = service.get_preview(date(2026, 5, 1))

        assert preview["period_start"] == date(2026, 4, 1)
        assert preview["period_end"] == date(2026, 6, 30)
        assert preview["income_cash"] == Decimal("100.10")
        assert preview["income_bank"] == Decimal("200.20")
        assert preview["expense_cash"] == Decimal("40.00")
        assert preview["expense_bank"] == Decimal("50.00")
        assert preview["expected_closing_cash"] == Decimal("60.10")
        assert preview["expected_closing_bank"] == Decimal("150.20")
        assert preview["status"] == FinancialSettlement.STATUS_DRAFT
    finally:
        engine.dispose()


def test_confirm_recalculates_and_freezes_snapshot(test_db_path, monkeypatch):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        _seed_activity(factory)
        draft = service.save_draft(
            target_date=date(2026, 5, 1),
            opening_cash=1000,
            opening_bank=2000,
            actual_closing_cash=1060.10,
            actual_closing_bank=2150.20,
            comment="draft",
        )
        assert draft.status == FinancialSettlement.STATUS_DRAFT

        # Confirm must recalculate the live activity instead of freezing the
        # previously saved draft totals.
        with factory() as session:
            session.add(
                Income(
                    amount=25.0,
                    income_type="Other",
                    payment_method="Cash",
                    payment_date=date(2026, 6, 10),
                    finance_period_start=date(2026, 4, 1),
                )
            )
            session.commit()

        confirmed = service.confirm(
            target_date=date(2026, 5, 1),
            opening_cash=1000,
            opening_bank=2000,
            actual_closing_cash=1085.10,
            actual_closing_bank=2150.20,
            comment="checked",
        )
        assert confirmed.status == FinancialSettlement.STATUS_CONFIRMED
        assert confirmed.income_cash == Decimal("125.10")
        assert confirmed.expected_closing_cash == Decimal("1085.10")
        assert confirmed.difference_cash == Decimal("0.00")
        assert confirmed.difference_bank == Decimal("0.00")
        assert confirmed.confirmed_at is not None

        # Later transaction edits do not mutate a confirmed audit snapshot.
        with factory() as session:
            session.add(
                Income(
                    amount=500.0,
                    income_type="Other",
                    payment_method="Cash",
                    payment_date=date(2026, 6, 11),
                    finance_period_start=date(2026, 4, 1),
                )
            )
            session.commit()

        preview = service.get_preview(date(2026, 5, 1))
        assert preview["income_cash"] == Decimal("125.10")
        assert preview["expected_closing_cash"] == Decimal("1085.10")
        assert preview["status"] == FinancialSettlement.STATUS_CONFIRMED

        with pytest.raises(ValueError, match="immutable"):
            service.save_draft(
                target_date=date(2026, 5, 1),
                opening_cash=1,
                opening_bank=1,
            )
    finally:
        engine.dispose()


def test_confirmation_requires_actual_balances_and_one_row_per_period(test_db_path, monkeypatch):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        with pytest.raises(ValueError, match="Actual closing"):
            service.confirm(
                target_date=date(2026, 5, 1),
                opening_cash=0,
                opening_bank=0,
                actual_closing_cash=None,
                actual_closing_bank=None,
            )

        service.save_draft(target_date=date(2026, 4, 1), opening_cash=10, opening_bank=20)
        service.save_draft(target_date=date(2026, 6, 1), opening_cash=30, opening_bank=40)
        with factory() as session:
            rows = session.query(FinancialSettlement).all()
            assert len(rows) == 1
            assert rows[0].finance_period_start == date(2026, 4, 1)
            assert rows[0].opening_cash == Decimal("30.00")
    finally:
        engine.dispose()


def test_settlement_ui_and_migration_contracts_are_wired():
    page_source = Path(
        "src/centermanager/ui/finance_workspace/financial_settlement_page.py"
    ).read_text(encoding="utf-8")
    shell_source = Path(
        "src/centermanager/ui/finance_workspace/finance_workspace_shell.py"
    ).read_text(encoding="utf-8")
    migration_source = Path(
        "migrations/versions/1e10a021_financial_settlement.py"
    ).read_text(encoding="utf-8")

    assert "Save Draft" in page_source
    assert "Confirm Settlement" in page_source
    assert '"settlement"' in shell_source
    assert "FinancialSettlementPage" in shell_source
    assert 'revision = "1e10a021"' in migration_source
    assert 'down_revision = "1e10a020"' in migration_source
    assert "uq_financial_settlement_period_start" in migration_source
