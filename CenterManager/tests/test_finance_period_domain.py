from datetime import date

import pytest

from centermanager.models.finance_period import FinancePeriod, FinancePeriodDefinition


def test_finance_period_validates_duration_range():
    assert FinancePeriod.validate_duration(1) == 1
    assert FinancePeriod.validate_duration(24) == 24
    with pytest.raises(ValueError):
        FinancePeriod.validate_duration(0)
    with pytest.raises(ValueError):
        FinancePeriod.validate_duration(25)


def test_finance_period_add_months_preserves_calendar_bounds():
    assert FinancePeriodDefinition.add_months(date(2026, 1, 1), 4) == date(2026, 5, 1)
    assert FinancePeriodDefinition.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_finance_period_bounds_are_inclusive():
    start, end = FinancePeriodDefinition.bounds_for(date(2026, 9, 1), 4)
    assert start == date(2026, 9, 1)
    assert end == date(2026, 12, 31)


def test_finance_period_for_date_uses_anchor_and_duration():
    anchor = date(2026, 9, 1)
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 12, 31), 4) == (
        date(2026, 9, 1),
        date(2026, 12, 31),
    )
    assert FinancePeriodDefinition.period_for_date(anchor, date(2027, 1, 1), 4) == (
        date(2027, 1, 1),
        date(2027, 4, 30),
    )


def test_finance_period_contains_effective_window():
    period = FinancePeriod(
        duration_months=4,
        status=FinancePeriod.STATUS_ACTIVE,
        effective_from=date(2026, 9, 1),
    )
    assert period.contains(date(2026, 9, 1))
    assert period.contains(date(2027, 1, 1))
