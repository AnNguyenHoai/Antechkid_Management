from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from centermanager.services.expense_service import ExpenseService, ExpenseValidationError


class FakeFinancePeriods:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def get_unique_effective(self, on_date):
        if self.error:
            raise self.error
        return self.result


class FakeProvider:
    def __init__(self, finance_periods):
        self._finance_periods = finance_periods

    def finance_periods(self, session):
        return self._finance_periods


def service_with(period=None, error=None):
    service = object.__new__(ExpenseService)
    service._repository_provider = FakeProvider(FakeFinancePeriods(period, error))
    return service


def test_completed_expense_requires_period_assignment():
    service = service_with(SimpleNamespace(id=17))
    assert service._resolve_posting_period_id(object(), date.today(), "Completed") == 17


def test_completed_expense_rejects_missing_period():
    service = service_with(None)
    with pytest.raises(ExpenseValidationError, match="No FinancePeriod"):
        service._resolve_posting_period_id(object(), date.today(), "Completed")


def test_completed_expense_rejects_future_posting_before_lookup():
    service = service_with(SimpleNamespace(id=17))
    with pytest.raises(ExpenseValidationError, match="future"):
        service._resolve_posting_period_id(object(), date.today() + timedelta(days=1), "Completed")


def test_pending_future_expense_is_allowed_and_assigned_when_period_exists():
    service = service_with(SimpleNamespace(id=21))
    assert service._resolve_posting_period_id(
        object(), date.today() + timedelta(days=1), "Pending"
    ) == 21


def test_pending_expense_may_remain_unassigned_without_covering_configuration():
    service = service_with(None)
    assert service._resolve_posting_period_id(object(), date.today(), "Pending") is None


def test_ambiguous_period_is_explicit_validation_error():
    service = service_with(error=ValueError("Multiple FinancePeriod configurations cover date."))
    with pytest.raises(ExpenseValidationError, match="Multiple FinancePeriod"):
        service._resolve_posting_period_id(object(), date.today(), "Completed")
