# -*- coding: utf-8 -*-
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from centermanager.dto.outstanding_dto import BALANCE_STATE_OWED, BALANCE_STATE_PREPAID
from centermanager.models.income import Income
from centermanager.models.session import SessionStatus
from centermanager.services.tuition_detail_service import TuitionDetailService


class _ContextSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _Repo:
    def __init__(self, *, by_id=None, rows=None, total=None):
        self.by_id = by_id
        self.rows = list(rows or [])
        self.total = total
        self.list_kwargs = None

    def get_by_id(self, _identity):
        return self.by_id

    def get_by_class(self, _class_id):
        return list(self.rows)

    def list_records(self, **kwargs):
        self.list_kwargs = kwargs
        return list(self.rows)

    def sum_active_tuition_for_enrollment(self, enrollment_id, *, as_of_date=None):
        assert enrollment_id == 71
        return self.total


class _Provider:
    def __init__(self, enrollment, sessions, payments, paid):
        self.enrollment_repo = _Repo(by_id=enrollment)
        self.session_repo = _Repo(rows=sessions)
        self.payment_repo = _Repo(rows=payments, total=paid)

    def enrollments(self, _session):
        return self.enrollment_repo

    def sessions(self, _session):
        return self.session_repo

    def incomes(self, _session):
        return self.payment_repo

    def classes(self, _session):
        raise AssertionError("eager class snapshot should be used")

    def students(self, _session):
        raise AssertionError("eager student snapshot should be used")


def _enrollment():
    enrollment = SimpleNamespace(
        id=71,
        student_id=9,
        class_id=4,
        agreed_course_fee=Decimal("3600000.0000"),
        planned_sessions=24,
        unit_fee=Decimal("150000.0000"),
        enrolled_from_session=1,
        enrolled_until_session=24,
        discount_amount=Decimal("0.0000"),
        student=SimpleNamespace(full_name="Nguyen Van A", student_code="HS009"),
        class_=SimpleNamespace(name="Python 01", course="Python Basic"),
        course_name="Python Basic",
    )
    enrollment.has_tuition_contract = True
    return enrollment


def _sessions(base: date):
    rows = []
    for number in range(1, 13):
        status = (
            SessionStatus.COMPLETED.value
            if number <= 10
            else SessionStatus.SCHEDULED.value
        )
        rows.append(
            SimpleNamespace(
                id=number,
                class_id=4,
                session_number=number,
                title=f"Lesson {number}",
                status=status,
                scheduled_date=base + timedelta(days=number - 1),
                actual_date=(base + timedelta(days=number - 1)) if number <= 10 else None,
            )
        )
    return rows


def _payment(amount=500000):
    return SimpleNamespace(
        id=301,
        payment_date=date(2026, 9, 10),
        amount=float(amount),
        payment_method="BANK",
        payment_period="2026-09",
        finance_period_start=date(2026, 9, 1),
        received_by="Admin",
        note="Tuition payment",
        status=Income.STATUS_ACTIVE,
    )


def _service(*, paid=Decimal("500000")):
    enrollment = _enrollment()
    provider = _Provider(
        enrollment,
        _sessions(date(2026, 9, 1)),
        [_payment(int(paid))],
        paid,
    )
    return TuitionDetailService(lambda: _ContextSession(), provider), provider


def test_detail_explains_accrual_payment_and_owed_balance():
    service, provider = _service(paid=Decimal("500000"))

    detail = service.get_detail(71, as_of_date=date(2026, 9, 15))

    assert detail.planned_sessions == 24
    assert detail.completed_sessions == 10
    assert detail.billable_sessions == 10
    assert detail.unit_fee == Decimal("150000.0000")
    assert detail.gross_accrued == Decimal("1500000.0000")
    assert detail.net_accrued == Decimal("1500000.0000")
    assert detail.paid == Decimal("500000")
    assert detail.balance == Decimal("1000000.0000")
    assert detail.balance_state == BALANCE_STATE_OWED
    assert sum(row.billing_contribution for row in detail.sessions) == detail.gross_accrued
    assert len([row for row in detail.sessions if row.billable]) == 10
    assert detail.payments[0].accounting_reference == (
        "Income #301 · Accounting period 2026-09-01"
    )
    assert provider.payment_repo.list_kwargs["enrollment_id"] == 71
    assert provider.payment_repo.list_kwargs["income_type"] == "Tuition"
    assert provider.payment_repo.list_kwargs["date_to"] == date(2026, 9, 15)
    assert provider.payment_repo.list_kwargs["status"] == Income.STATUS_ACTIVE


def test_detail_preserves_prepaid_as_signed_enrollment_balance():
    service, _ = _service(paid=Decimal("2000000"))

    detail = service.get_detail(71, as_of_date=date(2026, 9, 15))

    assert detail.net_accrued == Decimal("1500000.0000")
    assert detail.paid == Decimal("2000000")
    assert detail.balance == Decimal("-500000.0000")
    assert detail.balance_state == BALANCE_STATE_PREPAID
    assert detail.debt_amount == Decimal("0")
    assert detail.prepaid_amount == Decimal("500000.0000")


def test_detail_cutoff_and_non_billable_rows_are_explainable():
    service, provider = _service(paid=Decimal("0"))
    provider.session_repo.rows[3].status = SessionStatus.POSTPONED.value
    provider.session_repo.rows[4].status = SessionStatus.CANCELLED.value

    detail = service.get_detail(71, as_of_date=date(2026, 9, 6))

    assert detail.completed_sessions == 4
    assert detail.billable_sessions == 4
    assert detail.net_accrued == Decimal("600000.0000")
    by_number = {row.session_number: row for row in detail.sessions}
    assert by_number[4].billable is False
    assert "Postponed" in by_number[4].explanation
    assert by_number[5].billable is False
    assert "Cancelled" in by_number[5].explanation
    assert by_number[7].billable is False
    assert by_number[7].explanation == "Sau ngày chốt"


def test_ui_renders_service_read_model_without_tuition_arithmetic():
    root = Path(__file__).resolve().parents[1]
    dialog_source = (
        root / "src/centermanager/ui/finance_workspace/tuition_detail_dialog.py"
    ).read_text(encoding="utf-8")
    page_source = (
        root / "src/centermanager/ui/finance_workspace/outstanding_list_page.py"
    ).read_text(encoding="utf-8")

    assert "TuitionAccrualService" not in dialog_source
    assert "sum_active_tuition_for_enrollment" not in dialog_source
    assert "TuitionDetailService" in page_source
    assert "get_detail(" in page_source
    assert "TuitionAccrualService" not in page_source
