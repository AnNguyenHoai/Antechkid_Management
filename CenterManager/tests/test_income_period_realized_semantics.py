from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.models.finance_period import FinancePeriod
from centermanager.models.income import Income
from centermanager.services.income_service import IncomeService, IncomeValidationError


class _FinancePeriods:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error
        self.seen_date = None

    def get_unique_effective(self, reference_date: date):
        self.seen_date = reference_date
        if self._error is not None:
            raise self._error
        return self._result


class _Enrollments:
    def __init__(self, result: bool):
        self._result = result
        self.calls = []

    def exists_on_date(self, student_id: int, class_id: int, on_date: date) -> bool:
        self.calls.append((student_id, class_id, on_date))
        return self._result


class _Provider:
    def __init__(self, *, finance_periods=None, enrollments=None):
        self._finance_periods = finance_periods
        self._enrollments = enrollments

    def finance_periods(self, session):
        return self._finance_periods

    def enrollments(self, session):
        return self._enrollments


def _service(provider: _Provider) -> IncomeService:
    service = object.__new__(IncomeService)
    service._repository_provider = provider
    return service


def _income(*, payment_date: date, status: str = Income.STATUS_ACTIVE, deleted=False):
    return Income(
        amount=100_000,
        income_type="Other",
        payment_method="Cash",
        payment_date=payment_date,
        status=status,
        deleted_at=datetime(2026, 9, 23, 12, 0) if deleted else None,
    )


def test_realized_income_requires_active_non_deleted_and_posted_to_cutoff():
    cutoff = date(2026, 9, 23)

    assert IncomeService.is_realized(
        _income(payment_date=cutoff - timedelta(days=1)), as_of=cutoff
    )
    assert IncomeService.is_realized(_income(payment_date=cutoff), as_of=cutoff)
    assert not IncomeService.is_realized(
        _income(payment_date=cutoff + timedelta(days=1)), as_of=cutoff
    )
    assert not IncomeService.is_realized(
        _income(payment_date=cutoff, status=Income.STATUS_VOIDED), as_of=cutoff
    )
    assert not IncomeService.is_realized(
        _income(payment_date=cutoff, deleted=True), as_of=cutoff
    )


def test_default_realized_cutoff_and_posting_guard_use_application_clock():
    business_date = date(2026, 9, 23)
    fixed_now = datetime(2026, 9, 23, 8, 0, 0)
    set_clock(Clock(now_fn=lambda: fixed_now, today_fn=lambda: business_date))
    try:
        assert IncomeService.is_realized(_income(payment_date=business_date))
        assert not IncomeService.is_realized(
            _income(payment_date=business_date + timedelta(days=1))
        )
        IncomeService._validate_realized_posting_date(business_date)
        with pytest.raises(IncomeValidationError, match="future payment date"):
            IncomeService._validate_realized_posting_date(
                business_date + timedelta(days=1)
            )
    finally:
        reset_clock()


def test_period_resolution_uses_unique_covering_configuration_and_bucket_start():
    payment_date = date(2026, 9, 23)
    configuration = FinancePeriod(
        id=17,
        duration_months=1,
        status=FinancePeriod.STATUS_ACTIVE,
        effective_from=date(2026, 9, 15),
        effective_to=date(2026, 10, 14),
    )
    finance_repo = _FinancePeriods(result=configuration)
    service = _service(_Provider(finance_periods=finance_repo))

    resolved_config, period_start = service._resolve_finance_period(
        object(), payment_date
    )

    assert resolved_config is configuration
    assert period_start == date(2026, 9, 15)
    assert finance_repo.seen_date == payment_date


def test_period_resolution_rejects_uncovered_income_date():
    service = _service(_Provider(finance_periods=_FinancePeriods(result=None)))

    with pytest.raises(
        IncomeValidationError, match="No Finance period configuration covers"
    ):
        service._resolve_finance_period(object(), date(2026, 9, 23))


def test_period_resolution_translates_ambiguous_configuration_to_domain_error():
    service = _service(
        _Provider(
            finance_periods=_FinancePeriods(
                error=ValueError(
                    "Ambiguous Finance period configuration for 2026-09-23"
                )
            )
        )
    )

    with pytest.raises(IncomeValidationError, match="Ambiguous Finance period"):
        service._resolve_finance_period(object(), date(2026, 9, 23))


def test_enrollment_validation_is_evaluated_at_payment_date():
    payment_date = date(2026, 8, 31)
    enrollment_repo = _Enrollments(result=True)
    service = _service(_Provider(enrollments=enrollment_repo))

    assert service._check_student_enrolled_on(
        object(), student_id=3, class_id=9, payment_date=payment_date
    )
    assert enrollment_repo.calls == [(3, 9, payment_date)]


def test_audit_snapshot_carries_canonical_period_identity():
    income = _income(payment_date=date(2026, 9, 23))
    income.finance_period_id = 17
    income.finance_period_start = date(2026, 9, 15)

    snapshot = IncomeService._audit_snapshot(income)

    assert snapshot["finance_period_id"] == 17
    assert snapshot["finance_period_start"] == "2026-09-15"
