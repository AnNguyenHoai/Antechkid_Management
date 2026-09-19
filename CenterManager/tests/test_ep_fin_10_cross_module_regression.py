from datetime import date, datetime
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


TARGET_DATE = date(2026, 5, 1)
PERIOD_START = date(2026, 4, 1)


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


def test_draft_settlement_tracks_live_finance_activity_and_excludes_inactive_rows(
    test_db_path, monkeypatch
):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        with factory() as session:
            session.add_all(
                [
                    Income(
                        amount=100,
                        income_type="Other",
                        payment_method="Cash",
                        payment_date=date(2026, 4, 2),
                        finance_period_start=PERIOD_START,
                        status=Income.STATUS_ACTIVE,
                    ),
                    Income(
                        amount=50,
                        income_type="Other",
                        payment_method="Cash",
                        payment_date=date(2026, 4, 3),
                        finance_period_start=PERIOD_START,
                        status=Income.STATUS_VOIDED,
                        voided_at=datetime.utcnow(),
                        void_reason="regression fixture",
                    ),
                    Income(
                        amount=75,
                        income_type="Other",
                        payment_method="Bank Transfer",
                        payment_date=date(2026, 4, 4),
                        finance_period_start=PERIOD_START,
                        status=Income.STATUS_ACTIVE,
                        deleted_at=datetime.utcnow(),
                    ),
                    Expense(
                        category="Material",
                        amount=20,
                        payment_method="Cash",
                        status="Paid",
                        payment_date=date(2026, 4, 5),
                    ),
                    Expense(
                        category="Archived",
                        amount=30,
                        payment_method="Bank Transfer",
                        status="Paid",
                        payment_date=date(2026, 4, 6),
                        deleted_at=datetime.utcnow(),
                    ),
                ]
            )
            session.commit()

        service.save_draft(
            target_date=TARGET_DATE,
            opening_cash=1000,
            opening_bank=2000,
        )
        preview = service.get_preview(TARGET_DATE)
        assert preview["status"] == FinancialSettlement.STATUS_DRAFT
        assert preview["income_cash"] == Decimal("100.00")
        assert preview["income_bank"] == Decimal("0.00")
        assert preview["expense_cash"] == Decimal("20.00")
        assert preview["expense_bank"] == Decimal("0.00")
        assert preview["expected_closing_cash"] == Decimal("1080.00")
        assert preview["expected_closing_bank"] == Decimal("2000.00")

        # Cross-module mutation: Draft Settlement must read current live Finance
        # activity rather than the totals stored when the draft was saved.
        with factory() as session:
            session.add_all(
                [
                    Income(
                        amount=40,
                        income_type="Other",
                        payment_method="Bank Transfer",
                        payment_date=date(2026, 5, 10),
                        finance_period_start=PERIOD_START,
                        status=Income.STATUS_ACTIVE,
                    ),
                    Expense(
                        category="Rent",
                        amount=10,
                        payment_method="Bank Transfer",
                        status="Paid",
                        payment_date=date(2026, 5, 11),
                    ),
                ]
            )
            session.commit()

        refreshed = service.get_preview(TARGET_DATE)
        assert refreshed["income_cash"] == Decimal("100.00")
        assert refreshed["income_bank"] == Decimal("40.00")
        assert refreshed["expense_cash"] == Decimal("20.00")
        assert refreshed["expense_bank"] == Decimal("10.00")
        assert refreshed["expected_closing_cash"] == Decimal("1080.00")
        assert refreshed["expected_closing_bank"] == Decimal("2030.00")
    finally:
        engine.dispose()


def test_confirmed_settlement_freezes_snapshot_while_live_finance_continues(
    test_db_path, monkeypatch
):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        with factory() as session:
            session.add(
                Income(
                    amount=100,
                    income_type="Other",
                    payment_method="Cash",
                    payment_date=date(2026, 4, 2),
                    finance_period_start=PERIOD_START,
                    status=Income.STATUS_ACTIVE,
                )
            )
            session.commit()

        confirmed = service.confirm(
            target_date=TARGET_DATE,
            opening_cash=1000,
            opening_bank=2000,
            actual_closing_cash=1100,
            actual_closing_bank=2000,
        )
        assert confirmed.status == FinancialSettlement.STATUS_CONFIRMED
        assert confirmed.income_cash == Decimal("100.00")
        assert confirmed.expected_closing_cash == Decimal("1100.00")

        with factory() as session:
            session.add_all(
                [
                    Income(
                        amount=500,
                        income_type="Other",
                        payment_method="Cash",
                        payment_date=date(2026, 5, 12),
                        finance_period_start=PERIOD_START,
                        status=Income.STATUS_ACTIVE,
                    ),
                    Expense(
                        category="Material",
                        amount=50,
                        payment_method="Cash",
                        status="Paid",
                        payment_date=date(2026, 5, 13),
                    ),
                ]
            )
            session.commit()

        frozen = service.get_preview(TARGET_DATE)
        assert frozen["status"] == FinancialSettlement.STATUS_CONFIRMED
        assert frozen["income_cash"] == Decimal("100.00")
        assert frozen["expense_cash"] == Decimal("0.00")
        assert frozen["expected_closing_cash"] == Decimal("1100.00")
        assert frozen["difference_cash"] == Decimal("0.00")
    finally:
        engine.dispose()


def test_confirm_revalidates_difference_comment_after_live_activity_changes(
    test_db_path, monkeypatch
):
    engine, factory, service = _service_with_period(test_db_path, monkeypatch)
    try:
        # Actual balances are initially equal to the live expected balances.
        service.save_draft(
            target_date=TARGET_DATE,
            opening_cash=100,
            opening_bank=200,
            actual_closing_cash=100,
            actual_closing_bank=200,
        )

        # A new transaction arrives after the draft. Confirm must recalculate
        # first and enforce the comment invariant at the service boundary.
        with factory() as session:
            session.add(
                Income(
                    amount=10,
                    income_type="Other",
                    payment_method="Cash",
                    payment_date=date(2026, 5, 15),
                    finance_period_start=PERIOD_START,
                    status=Income.STATUS_ACTIVE,
                )
            )
            session.commit()

        with pytest.raises(ValueError, match="Comment is required"):
            service.confirm(
                target_date=TARGET_DATE,
                opening_cash=100,
                opening_bank=200,
                actual_closing_cash=100,
                actual_closing_bank=200,
                comment="   ",
            )

        draft = service.get_settlement(TARGET_DATE)
        assert draft is not None
        assert draft.status == FinancialSettlement.STATUS_DRAFT

        confirmed = service.confirm(
            target_date=TARGET_DATE,
            opening_cash=100,
            opening_bank=200,
            actual_closing_cash=100,
            actual_closing_bank=200,
            comment="Late cash income reviewed",
        )
        assert confirmed.status == FinancialSettlement.STATUS_CONFIRMED
        assert confirmed.expected_closing_cash == Decimal("110.00")
        assert confirmed.difference_cash == Decimal("-10.00")
        assert confirmed.comment == "Late cash income reviewed"
    finally:
        engine.dispose()


def test_cross_module_refresh_period_and_student_read_only_contracts():
    shell = Path(
        "src/centermanager/ui/finance_workspace/finance_workspace_shell.py"
    ).read_text(encoding="utf-8")
    income_service = Path("src/centermanager/services/income_service.py").read_text(
        encoding="utf-8"
    )
    expense_service = Path("src/centermanager/services/expense_service.py").read_text(
        encoding="utf-8"
    )
    student_financial = Path(
        "src/centermanager/ui/student_workspace/student_financial_widget.py"
    ).read_text(encoding="utf-8")

    # One mutation event refreshes every live Finance surface through one shared
    # canonical period context, including Settlement.
    assert "self._event_bus.register(FinanceDataChanged" in shell
    assert "def _on_finance_data_changed" in shell
    for page_name in (
        "self.dashboard_page,",
        "self.income_page,",
        "self.expense_page,",
        "self.outstanding_page,",
        "self.settlement_page,",
    ):
        assert page_name in shell
    assert "target_date=target_date" in shell
    assert "period_start=period_start" in shell
    assert "period_end=period_end" in shell
    assert "period_configured=period_configured" in shell

    # Income and Expense are mutation publishers feeding that shared refresh.
    assert "FinanceDataChanged(entity=\"income\"" in income_service
    assert "FinanceDataChanged(entity=\"expense\"" in expense_service

    # Student Financial is a read model only; Finance owns money mutations.
    assert "Collect Tuition" not in student_financial
    assert "CollectTuitionDialog" not in student_financial
    assert ".create_income(" not in student_financial
    assert ".update_income(" not in student_financial
    assert ".void_income(" not in student_financial
    assert ".delete_income(" not in student_financial
    assert "open_finance_clicked" in student_financial
