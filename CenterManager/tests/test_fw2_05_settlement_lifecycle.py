from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.models.finance_period import FinancePeriod
from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.services.financial_settlement_service import FinancialSettlementService


class _Session:
    def __init__(self):
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.commit_count += 1


class _SessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self.session


class _FinancePeriods:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.seen = None

    def get_unique_effective(self, target):
        self.seen = target
        if self.error is not None:
            raise self.error
        return self.result


class _Settlements:
    def __init__(self, row=None):
        self.row = row
        self.added = []
        self.refreshed = []
        self.flush_count = 0

    def get_by_period_start(self, period_start):
        return self.row

    def add(self, row):
        if row.id is None:
            row.id = 41
        self.row = row
        self.added.append(row)
        return row

    def flush(self):
        self.flush_count += 1

    def refresh(self, row):
        self.refreshed.append(row)
        return row


class _IncomeAggregate:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def aggregate_active_amounts_by_payment_method(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class _ExpenseAggregate:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def aggregate_realized_amounts_by_payment_method(self, **kwargs):
        self.calls.append(kwargs)
        return self.rows


class _Provider:
    def __init__(self, *, periods=None, settlements=None, incomes=None, expenses=None):
        self.periods = periods
        self.settlements = settlements
        self.incomes_repo = incomes
        self.expenses_repo = expenses

    def finance_periods(self, session):
        return self.periods

    def financial_settlements(self, session):
        return self.settlements

    def incomes(self, session):
        return self.incomes_repo

    def expenses(self, session):
        return self.expenses_repo


class _Audit:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def record_in_session(self, session, **kwargs):
        if self.error is not None:
            raise self.error
        self.calls.append((session, kwargs))


def _service(provider, session=None, audit=None):
    session = session or _Session()
    service = FinancialSettlementService(
        _SessionFactory(session),
        repository_provider=provider,
        audit_service=audit or _Audit(),
    )
    service._require_admin = lambda: None
    return service, session


def _confirmed_row():
    return FinancialSettlement(
        id=9,
        finance_period_start=date(2026, 9, 15),
        finance_period_end=date(2026, 10, 14),
        status=FinancialSettlement.STATUS_CONFIRMED,
        confirmed_at=datetime(2026, 10, 15, 8, 0, 0),
    )


def test_period_resolution_uses_unique_clamped_canonical_bounds():
    config = FinancePeriod(
        id=7,
        duration_months=1,
        status=FinancePeriod.STATUS_INACTIVE,
        effective_from=date(2026, 8, 15),
        effective_to=date(2026, 8, 31),
    )
    periods = _FinancePeriods(result=config)
    service, _ = _service(_Provider(periods=periods))

    start, end = service._resolve_period(object(), date(2026, 8, 20))

    assert start == date(2026, 8, 15)
    assert end == date(2026, 8, 31)
    assert periods.seen == date(2026, 8, 20)


def test_complete_ledger_aggregation_uses_repository_sums_without_row_limits():
    incomes = _IncomeAggregate(
        [("Cash", Decimal("120.00")), ("Bank Transfer", Decimal("80.00"))]
    )
    expenses = _ExpenseAggregate(
        [("TÀI KHOẢN CÁ NHÂN", Decimal("20.00")), ("Bank", Decimal("10.00"))]
    )
    service, _ = _service(_Provider(incomes=incomes, expenses=expenses))

    totals = service._aggregate_activity(
        object(), date(2026, 9, 15), date(2026, 10, 14)
    )

    assert totals == {
        "income_cash": Decimal("120.00"),
        "income_bank": Decimal("80.00"),
        "expense_cash": Decimal("20.00"),
        "expense_bank": Decimal("10.00"),
    }
    assert incomes.calls == [{
        "finance_period_start": date(2026, 9, 15),
        "date_from": date(2026, 9, 15),
        "date_to": date(2026, 10, 14),
    }]
    assert expenses.calls == [{
        "date_from": date(2026, 9, 15),
        "date_to": date(2026, 10, 14),
        "realized_only": True,
    }]


def test_confirm_recalculates_snapshot_and_commits_audit_atomically():
    session = _Session()
    settlements = _Settlements()
    audit = _Audit()
    service, _ = _service(
        _Provider(settlements=settlements), session=session, audit=audit
    )
    service._resolve_period = lambda _session, _target: (
        date(2026, 9, 15), date(2026, 10, 14)
    )
    service._aggregate_activity = lambda _session, _start, _end: {
        "income_cash": Decimal("100.00"),
        "income_bank": Decimal("50.00"),
        "expense_cash": Decimal("20.00"),
        "expense_bank": Decimal("10.00"),
    }
    fixed_now = datetime(2026, 10, 15, 9, 30, 0)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_now.date()))
    try:
        row = service.confirm(
            target_date=date(2026, 9, 23),
            opening_cash=10,
            opening_bank=5,
            actual_closing_cash=90,
            actual_closing_bank=45,
        )
    finally:
        reset_clock()

    assert row.status == FinancialSettlement.STATUS_CONFIRMED
    assert row.confirmed_at == fixed_now
    assert row.expected_closing_cash == Decimal("90.00")
    assert row.expected_closing_bank == Decimal("45.00")
    assert row.difference_cash == Decimal("0.00")
    assert row.difference_bank == Decimal("0.00")
    assert settlements.flush_count == 1
    assert session.commit_count == 1
    assert len(audit.calls) == 1
    assert audit.calls[0][1]["action"] == "CONFIRM"
    assert audit.calls[0][1]["details"]["settlement_id"] == 41


def test_confirm_requires_actual_balances_and_comment_for_nonzero_difference():
    settlements = _Settlements()
    service, session = _service(_Provider(settlements=settlements))
    service._resolve_period = lambda _session, _target: (
        date(2026, 9, 15), date(2026, 10, 14)
    )
    service._aggregate_activity = lambda _session, _start, _end: {
        "income_cash": Decimal("0.00"),
        "income_bank": Decimal("0.00"),
        "expense_cash": Decimal("0.00"),
        "expense_bank": Decimal("0.00"),
    }

    with pytest.raises(ValueError, match="Actual closing cash and bank"):
        service.confirm(
            target_date=date(2026, 9, 23),
            actual_closing_cash=None,
            actual_closing_bank=0,
        )
    with pytest.raises(ValueError, match="Comment is required"):
        service.confirm(
            target_date=date(2026, 9, 23),
            actual_closing_cash=1,
            actual_closing_bank=0,
        )
    assert session.commit_count == 0


def test_confirm_audit_failure_prevents_commit_and_therefore_period_closure():
    session = _Session()
    settlements = _Settlements()
    audit = _Audit(error=RuntimeError("audit unavailable"))
    service, _ = _service(
        _Provider(settlements=settlements), session=session, audit=audit
    )
    service._resolve_period = lambda _session, _target: (
        date(2026, 9, 15), date(2026, 10, 14)
    )
    service._aggregate_activity = lambda _session, _start, _end: {
        "income_cash": Decimal("0.00"),
        "income_bank": Decimal("0.00"),
        "expense_cash": Decimal("0.00"),
        "expense_bank": Decimal("0.00"),
    }

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.confirm(
            target_date=date(2026, 9, 23),
            actual_closing_cash=0,
            actual_closing_bank=0,
        )

    assert settlements.flush_count == 1
    assert session.commit_count == 0


def test_reopen_requires_reason_and_atomically_audits_confirmed_to_draft():
    row = _confirmed_row()
    settlements = _Settlements(row=row)
    audit = _Audit()
    service, session = _service(
        _Provider(settlements=settlements), audit=audit
    )
    service._resolve_period = lambda _session, _target: (
        date(2026, 9, 15), date(2026, 10, 14)
    )
    fixed_now = datetime(2026, 10, 16, 8, 45, 0)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: fixed_now.date()))
    try:
        with pytest.raises(ValueError, match="Reopen reason"):
            service.reopen(target_date=date(2026, 9, 23), reason="   ")
        reopened = service.reopen(
            target_date=date(2026, 9, 23),
            reason="Correct bank reconciliation",
        )
    finally:
        reset_clock()

    assert reopened.status == FinancialSettlement.STATUS_DRAFT
    assert reopened.confirmed_at is None
    assert session.commit_count == 1
    assert len(audit.calls) == 1
    details = audit.calls[0][1]["details"]
    assert audit.calls[0][1]["action"] == "REOPEN"
    assert details["period_start"] == "2026-09-15"
    assert details["previous_settlement_id"] == 9
    assert details["previous_status"] == FinancialSettlement.STATUS_CONFIRMED
    assert details["reason"] == "Correct bank reconciliation"
    assert details["reopened_at"] == fixed_now.isoformat()


def test_reopen_rejects_missing_or_nonconfirmed_settlement():
    service, session = _service(_Provider(settlements=_Settlements(row=None)))
    service._resolve_period = lambda _session, _target: (
        date(2026, 9, 15), date(2026, 10, 14)
    )
    with pytest.raises(ValueError, match="No financial settlement"):
        service.reopen(target_date=date(2026, 9, 23), reason="Admin correction")

    draft = FinancialSettlement(
        id=10,
        finance_period_start=date(2026, 9, 15),
        finance_period_end=date(2026, 10, 14),
        status=FinancialSettlement.STATUS_DRAFT,
    )
    service._repository_provider.settlements = _Settlements(row=draft)
    with pytest.raises(ValueError, match="Only a CONFIRMED"):
        service.reopen(target_date=date(2026, 9, 23), reason="Admin correction")
    assert session.commit_count == 0
