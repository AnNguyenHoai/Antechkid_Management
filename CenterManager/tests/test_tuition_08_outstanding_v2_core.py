# -*- coding: utf-8 -*-
"""TUITION-08 — Enrollment-centric Outstanding V2 regression coverage."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.outstanding_service import OutstandingService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SOURCE = PROJECT_ROOT / "src" / "centermanager" / "services" / "outstanding_service.py"


class _SessionContext:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _EnrollmentRepo:
    def __init__(self, enrollments):
        self._items = list(enrollments)

    def get_by_id(self, enrollment_id):
        return next((item for item in self._items if item.id == enrollment_id), None)

    def get_by_student_and_class(self, student_id, class_id):
        return [
            item
            for item in self._items
            if item.student_id == student_id and item.class_id == class_id
        ]

    def list_for_outstanding(self, **kwargs):
        items = list(self._items)
        if kwargs.get("class_id") is not None:
            items = [item for item in items if item.class_id == kwargs["class_id"]]
        if kwargs.get("student_id") is not None:
            items = [item for item in items if item.student_id == kwargs["student_id"]]
        search = (kwargs.get("search_text") or "").casefold()
        if search:
            items = [
                item
                for item in items
                if search in item.student.full_name.casefold()
                or search in item.student.student_code.casefold()
                or search in item.class_.name.casefold()
            ]
        return items, len(items)


class _SessionRepo:
    def __init__(self, sessions_by_class):
        self._items = sessions_by_class

    def get_by_class(self, class_id):
        return list(self._items.get(class_id, []))


class _IncomeRepo:
    def __init__(self, payments):
        self._payments = payments
        self.calls = []

    def sum_active_tuition_for_enrollment(self, enrollment_id, as_of_date=None):
        self.calls.append((enrollment_id, as_of_date))
        return sum(
            (
                amount
                for paid_on, amount in self._payments.get(enrollment_id, [])
                if as_of_date is None or paid_on <= as_of_date
            ),
            Decimal("0"),
        )


class _NoPeriodRepo:
    def get_unique_effective(self, _target):
        return None


class _Provider:
    def __init__(self, enrollments, sessions_by_class, payments):
        self.enrollment_repo = _EnrollmentRepo(enrollments)
        self.session_repo = _SessionRepo(sessions_by_class)
        self.income_repo = _IncomeRepo(payments)
        self.period_repo = _NoPeriodRepo()

    def enrollments(self, _session):
        return self.enrollment_repo

    def sessions(self, _session):
        return self.session_repo

    def incomes(self, _session):
        return self.income_repo

    def finance_periods(self, _session):
        return self.period_repo


def _student(student_id=10):
    return SimpleNamespace(
        id=student_id,
        full_name=f"Student {student_id}",
        student_code=f"ST{student_id}",
    )


def _class(class_id=20):
    return SimpleNamespace(id=class_id, name=f"Class {class_id}", course="Python")


def _enrollment(
    enrollment_id,
    *,
    student=None,
    class_obj=None,
    unit_fee="150000",
    planned_sessions=10,
    start_session=1,
    end_session=10,
):
    student = student or _student()
    class_obj = class_obj or _class()
    return SimpleNamespace(
        id=enrollment_id,
        student_id=student.id,
        class_id=class_obj.id,
        student=student,
        class_=class_obj,
        class_name=class_obj.name,
        course_name=class_obj.course,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        agreed_course_fee=Decimal(unit_fee) * Decimal(planned_sessions),
        planned_sessions=planned_sessions,
        unit_fee=Decimal(unit_fee),
        enrolled_from_session=start_session,
        enrolled_until_session=end_session,
        discount_amount=Decimal("0"),
        has_tuition_contract=True,
    )


def _completed(class_id, number, on_date):
    return SimpleNamespace(
        class_id=class_id,
        session_number=number,
        status=SessionStatus.COMPLETED.value,
        scheduled_date=on_date,
        actual_date=on_date,
    )


def _service(enrollments, sessions_by_class, payments):
    provider = _Provider(enrollments, sessions_by_class, payments)
    service = OutstandingService(lambda: _SessionContext(), provider)
    return service, provider


def test_acceptance_formula_accrued_1500000_paid_1200000_outstanding_300000():
    enrollment = _enrollment(101)
    sessions = [_completed(20, number, date(2026, 1, number)) for number in range(1, 11)]
    service, provider = _service(
        [enrollment],
        {20: sessions},
        {101: [(date(2026, 2, 10), Decimal("1200000"))]},
    )

    dto = service.get_outstanding_for_enrollment(
        student_id=10,
        class_id=20,
        enrollment_id=101,
        as_of_date=date(2026, 3, 1),
    )

    assert dto is not None
    assert dto.enrollment_id == 101
    assert dto.expected_tuition == Decimal("1500000.0000")
    assert dto.paid == Decimal("1200000")
    assert dto.outstanding == Decimal("300000.0000")
    assert dto.status == "Partial"
    assert provider.income_repo.calls == [(101, date(2026, 3, 1))]


def test_reenrollments_in_same_student_and_class_keep_independent_balances():
    student = _student()
    class_obj = _class()
    first = _enrollment(
        101,
        student=student,
        class_obj=class_obj,
        unit_fee="100000",
        planned_sessions=5,
        start_session=1,
        end_session=5,
    )
    second = _enrollment(
        202,
        student=student,
        class_obj=class_obj,
        unit_fee="200000",
        planned_sessions=5,
        start_session=6,
        end_session=10,
    )
    sessions = [_completed(20, number, date(2026, 1, number)) for number in range(1, 11)]
    service, _ = _service(
        [first, second],
        {20: sessions},
        {
            101: [(date(2026, 1, 20), Decimal("100000"))],
            202: [(date(2026, 1, 20), Decimal("800000"))],
        },
    )

    rows, total, _stats = service.get_outstanding_page(
        as_of_date=date(2026, 2, 1),
        offset=0,
        limit=None,
        sort_by="expected_tuition",
        ascending=True,
    )

    assert total == 2
    assert [row.enrollment_id for row in rows] == [101, 202]
    assert rows[0].outstanding == Decimal("400000.0000")
    assert rows[1].outstanding == Decimal("200000.0000")

    with pytest.raises(ValueError, match="Multiple Enrollment contracts"):
        service.get_outstanding_for_enrollment(
            student_id=10,
            class_id=20,
            as_of_date=date(2026, 2, 1),
        )


def test_as_of_date_is_shared_cutoff_for_accrual_and_payment():
    enrollment = _enrollment(101, unit_fee="100000", planned_sessions=2, end_session=2)
    sessions = [
        _completed(20, 1, date(2026, 1, 5)),
        _completed(20, 2, date(2026, 2, 5)),
    ]
    service, provider = _service(
        [enrollment],
        {20: sessions},
        {
            101: [
                (date(2026, 1, 6), Decimal("30000")),
                (date(2026, 2, 6), Decimal("70000")),
            ]
        },
    )

    dto = service.get_outstanding_for_enrollment(
        10,
        20,
        enrollment_id=101,
        as_of_date=date(2026, 1, 31),
    )

    assert dto.expected_tuition == Decimal("100000.0000")
    assert dto.paid == Decimal("30000")
    assert dto.outstanding == Decimal("70000.0000")
    assert provider.income_repo.calls[-1] == (101, date(2026, 1, 31))


def test_missing_finance_period_does_not_disable_core_balance_calculation():
    enrollment = _enrollment(101, unit_fee="100000", planned_sessions=1, end_session=1)
    service, _ = _service(
        [enrollment],
        {20: [_completed(20, 1, date(2026, 1, 5))]},
        {101: []},
    )

    rows, total, stats = service.get_outstanding_page(
        on_date=date(2026, 1, 31),
        as_of_date=date(2026, 1, 31),
        limit=None,
    )

    assert total == 1
    assert rows[0].expected_tuition == Decimal("100000.0000")
    assert stats["total_expected"] == Decimal("100000.0000")


def test_unresolved_historical_contract_never_invents_tuition():
    enrollment = _enrollment(101)
    enrollment.has_tuition_contract = False
    enrollment.agreed_course_fee = None
    enrollment.unit_fee = None
    service, _ = _service(
        [enrollment],
        {20: [_completed(20, 1, date(2026, 1, 5))]},
        {101: []},
    )

    dto = service.get_outstanding_for_enrollment(
        10,
        20,
        enrollment_id=101,
        as_of_date=date(2026, 1, 31),
    )

    assert dto.tuition_configured is False
    assert dto.expected_tuition == Decimal("0")
    assert dto.status == "No Tuition Configured"


def test_outstanding_source_reuses_tuition06_and_tuition07_without_legacy_fee_formula():
    source = SERVICE_SOURCE.read_text(encoding="utf-8")

    assert "TuitionAccrualService.calculate_from_records" in source
    assert "sum_active_tuition_for_enrollment" in source
    assert "ClassFeeHistory" not in source
    assert "get_tuition_sum_grouped" not in source
    assert "get_fee_for_period" not in source
