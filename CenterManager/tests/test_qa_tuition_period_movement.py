"""TUITION-PERIOD-01: enrollment-based movements from canonical snapshots/ledger."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from centermanager.services.tuition_period_movement_service import (
    TuitionPeriodMovementService, TuitionPeriodMovement,
    TuitionPeriodReport,
)


class FakeSession:
    def __enter__(self): return self
    def __exit__(self, typ, val, tb): return False


def contract(eid, name="Student"):
    return SimpleNamespace(
        id=eid, student_id=eid + 100, class_id=eid + 1000,
        student=SimpleNamespace(full_name=name, student_code=f"S{eid}"),
        class_=SimpleNamespace(name=f"Class-{eid}"),
    )


def component(on, amount, source="INCOME"):
    return SimpleNamespace(effective_date=on, amount=Decimal(str(amount)), source=source)


def make_svc(contracts, accruals, components):
    class EnrollmentRepo:
        def list_for_outstanding(self, **kw):
            return contracts, len(contracts)
    class IncomeRepo:
        def list_active_tuition_settlement_components(self, eid, *, as_of_date):
            assert as_of_date == date(2026, 11, 30)
            return [x for x in components.get(eid, []) if x.effective_date <= as_of_date]
    provider = SimpleNamespace(
        enrollments=lambda _: EnrollmentRepo(),
        incomes=lambda _: IncomeRepo(),
    )
    outstanding = SimpleNamespace(
        _session_factory=FakeSession,
        _repository_provider=provider,
        _calculate_accrued=lambda session, contract, *, as_of_date:
            accruals[(contract.id, as_of_date)],
    )
    return TuitionPeriodMovementService(outstanding)


NOV_START = date(2026, 11, 1)
NOV_END = date(2026, 11, 30)
OCT_END = date(2026, 10, 31)


def test_real_period_movements_include_refund_credit_and_transfer_and_reconcile():
    svc = make_svc(
        [contract(1)],
        {(1, OCT_END): (Decimal(400), True),
         (1, NOV_END): (Decimal(900), True)},
        {1: [component(date(2026, 10, 10), 250),
             component(date(2026, 11, 4), 300),
             component(date(2026, 11, 5), -50),  # refunded Income
             component(date(2026, 11, 6), 75, "TUITION_ADJUSTMENT"),
             component(date(2026, 11, 8), -25, "ENROLLMENT_TRANSFER")]},
    )
    report = svc.build(period_start=NOV_START, period_end=NOV_END)
    row, = report.rows
    assert row.opening == 150
    assert row.accrued == 500
    assert row.received == 250
    assert row.adjustments == 50
    assert row.closing == 350
    assert row.reconciles
    totals = report.totals
    assert totals["opening"] + totals["accrued"] - totals["received"] - totals["adjustments"] == totals["closing"]


def test_two_course_wallets_never_net_receivable_against_prepaid():
    svc = make_svc(
        [contract(1), contract(2)],
        {(1, OCT_END): (Decimal(500), True),
         (1, NOV_END): (Decimal(700), True),
         (2, OCT_END): (Decimal(100), True),
         (2, NOV_END): (Decimal(100), True)},
        {1: [component(date(2026, 10, 20), 300)],
         2: [component(date(2026, 10, 20), 250)]},
    )
    report = svc.build(period_start=NOV_START, period_end=NOV_END)
    assert [r.enrollment_id for r in report.rows] == [1, 2]
    assert report.totals["closing"] == 250  # signed
    assert report.totals["receivable"] == 400
    assert report.totals["prepaid"] == 150


def test_unconfigured_contract_never_presents_its_tuition_as_zero():
    svc = make_svc(
        [contract(1)],
        {(1, OCT_END): (Decimal(0), False),
         (1, NOV_END): (Decimal(0), False)},
        {1: [component(date(2026, 11, 3), 350)]},
    )
    report = svc.build(period_start=NOV_START, period_end=NOV_END)
    row, = report.rows
    assert row.opening is row.accrued is row.closing is None
    assert row.received == 350
    assert report.totals["unconfigured"] == 1
    assert report.totals["unresolved_received"] == 350
    assert report.totals["received"] == 0
    assert report.totals["closing"] == 0


def test_duplicate_enrollment_rows_are_not_double_counted():
    item = contract(1)
    svc = make_svc(
        [item, item],
        {(1, OCT_END): (Decimal(100), True),
         (1, NOV_END): (Decimal(200), True)},
        {1: []},
    )
    report = svc.build(period_start=NOV_START, period_end=NOV_END)
    assert len(report.rows) == 1


def test_invalid_period_refuses_unsafe_opening():
    svc = make_svc([], {}, {})
    with pytest.raises(ValueError):
        svc.build(period_start=NOV_END, period_end=NOV_START)
    with pytest.raises(ValueError):
        svc.build(period_start=date.min, period_end=NOV_END)


def test_settlement_reader_is_required_not_silently_ignored():
    svc = make_svc([contract(1)], {}, {})
    svc._outstanding._repository_provider.incomes = lambda _: object()
    with pytest.raises(RuntimeError, match="Canonical signed"):
        svc.build(period_start=NOV_START, period_end=NOV_END)


def test_dialog_csv_contains_signed_components_and_exact_enrollment(qapp):
    from centermanager.ui.finance_workspace.tuition_period_movement_dialog import (
        TuitionPeriodMovementDialog,
    )
    svc = make_svc(
        [contract(1)],
        {(1, OCT_END): (Decimal(100), True),
         (1, NOV_END): (Decimal(200), True)},
        {1: [component(date(2026, 10, 5), 50),
             component(date(2026, 11, 5), -25)]},
    )
    dialog = TuitionPeriodMovementDialog(
        svc._outstanding, NOV_START, NOV_END,
    )
    assert dialog.table.rowCount() == 1
    assert dialog.table.columnCount() == 8
    assert dialog.table.horizontalScrollBarPolicy().name == "ScrollBarAsNeeded"
    assert "Enrollment" in dialog.to_csv()
    assert "-25" in dialog.to_csv()
    dialog.close()


def test_monthly_cutover_uses_prior_closing_as_next_opening():
    """Contract never resets when a month changes; dates are inclusive."""
    enrollment = contract(1)
    class FlexibleIncome:
        def __init__(self):
            self.events = [
                component(date(2026, 10, 31), 100),
                component(date(2026, 11, 1), 75),
                component(date(2026, 11, 30), 25),
                component(date(2026, 12, 1), 50),
            ]
        def list_active_tuition_settlement_components(self, eid, *, as_of_date):
            return [x for x in self.events if x.effective_date <= as_of_date]
    income = FlexibleIncome()
    provider = SimpleNamespace(
        enrollments=lambda _: SimpleNamespace(
            list_for_outstanding=lambda **kw: ([enrollment], 1)
        ),
        incomes=lambda _: income,
    )
    daily_earned = {
        date(2026, 10, 31): 500,
        date(2026, 11, 30): 900,
        date(2026, 12, 31): 1300,
    }
    source = SimpleNamespace(
        _session_factory=FakeSession,
        _repository_provider=provider,
        _calculate_accrued=lambda session, contract, *, as_of_date:
            (Decimal(daily_earned[as_of_date]), True),
    )
    svc = TuitionPeriodMovementService(source)
    nov = svc.build(period_start=date(2026, 11, 1), period_end=date(2026, 11, 30))
    dec = svc.build(period_start=date(2026, 12, 1), period_end=date(2026, 12, 31))
    assert nov.rows[0].opening == 400
    assert nov.rows[0].received == 100
    assert nov.rows[0].closing == 700
    assert dec.rows[0].opening == nov.rows[0].closing
    assert dec.rows[0].received == 50
    assert dec.rows[0].closing == 1050


def test_unknown_settlement_type_fails_closed():
    svc = make_svc(
        [contract(1)],
        {(1, OCT_END): (Decimal(0), True),
         (1, NOV_END): (Decimal(0), True)},
        {1: [component(NOV_START, 5, "UNKNOWN_LEDGER_TYPE")]},
    )
    with pytest.raises(RuntimeError, match="Unsupported tuition settlement"):
        svc.build(period_start=NOV_START, period_end=NOV_END)
