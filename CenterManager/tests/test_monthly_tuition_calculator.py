"""Pure monthly tuition calculator regression tests."""
from datetime import date, timedelta

import pytest

from centermanager.services.monthly_tuition_calculator import (
    allocate_monthly_tuition,
    cancellation_credit,
    tuition_due_from,
)


@pytest.mark.parametrize("count", [8, 9, 10])
def test_exact_monthly_total_and_deterministic_allocation(count):
    days = [date(2026, 11, 1) + timedelta(days=i) for i in range(count)]
    expected = allocate_monthly_tuition(800_000, days)
    assert sum(item.amount_vnd for item in expected) == 800_000
    assert expected == allocate_monthly_tuition(800_000, list(reversed(days)))
    assert max(x.amount_vnd for x in expected) - min(x.amount_vnd for x in expected) <= 1


def test_midmonth_and_cancelled_session_value():
    days = [date(2026, 11, i) for i in range(1, 10)]
    allocations = allocate_monthly_tuition(800_000, days)
    assert tuition_due_from(allocations, date(2026, 11, 5)) == sum(
        item.amount_vnd for item in allocations[4:]
    )
    assert cancellation_credit(allocations, date(2026, 11, 1)) == 88_889


def test_zero_sessions_duplicate_dates_and_cross_month_rejected():
    with pytest.raises(ValueError):
        allocate_monthly_tuition(800_000, [])
    with pytest.raises(ValueError):
        allocate_monthly_tuition(800_000, [date(2026, 11, 1)] * 2)
    with pytest.raises(ValueError):
        allocate_monthly_tuition(800_000, [date(2026, 11, 1), date(2026, 12, 1)])


@pytest.mark.parametrize("fee", [-1, 1.5, True])
def test_invalid_money_rejected(fee):
    with pytest.raises((TypeError, ValueError)):
        allocate_monthly_tuition(fee, [date(2026, 11, 1)])


def test_zero_fee_and_after_month_start():
    days = [date(2026, 11, 1), date(2026, 11, 8)]
    allocations = allocate_monthly_tuition(0, days)
    assert tuition_due_from(allocations, date(2026, 12, 1)) == 0
