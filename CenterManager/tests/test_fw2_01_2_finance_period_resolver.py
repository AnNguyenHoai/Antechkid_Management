from datetime import date

import pytest

from centermanager.models.finance_period import FinancePeriod, FinancePeriodDefinition


def config(start, *, duration=1, end=None, config_id=1):
    period = FinancePeriod(
        duration_months=duration,
        effective_from=start,
        effective_to=end,
        status=FinancePeriod.STATUS_ACTIVE if end is None else FinancePeriod.STATUS_INACTIVE,
    )
    period.id = config_id
    return period


def test_resolves_normal_bucket_from_non_month_anchor():
    resolved = FinancePeriodDefinition.resolved_for_configuration(
        config(date(2026, 9, 15)), date(2026, 10, 2)
    )
    assert resolved.configuration_id == 1
    assert resolved.period_start == date(2026, 9, 15)
    assert resolved.period_end == date(2026, 10, 14)
    assert resolved.contains(date(2026, 10, 2))


def test_clamps_natural_bucket_at_configuration_transition_f20():
    old = config(date(2026, 8, 15), end=date(2026, 8, 31), config_id=10)
    resolved = FinancePeriodDefinition.resolved_for_configuration(old, date(2026, 8, 31))
    assert resolved.period_start == date(2026, 8, 15)
    assert resolved.period_end == date(2026, 8, 31)

    new = config(date(2026, 9, 1), config_id=11)
    next_resolved = FinancePeriodDefinition.resolved_for_configuration(new, date(2026, 9, 1))
    assert next_resolved.period_start == date(2026, 9, 1)
    assert resolved.period_end < next_resolved.period_start


def test_multi_month_duration_remains_supported():
    resolved = FinancePeriodDefinition.resolved_for_configuration(
        config(date(2026, 1, 10), duration=3), date(2026, 5, 20)
    )
    assert resolved.period_start == date(2026, 4, 10)
    assert resolved.period_end == date(2026, 7, 9)


def test_end_of_month_anchor_keeps_existing_calendar_math():
    resolved = FinancePeriodDefinition.resolved_for_configuration(
        config(date(2024, 1, 31)), date(2024, 2, 29)
    )
    assert resolved.period_start == date(2024, 2, 29)
    assert resolved.period_end == date(2024, 3, 28)


def test_target_outside_configuration_is_rejected():
    period = config(date(2026, 8, 15), end=date(2026, 8, 31))
    with pytest.raises(ValueError, match="outside"):
        FinancePeriodDefinition.resolved_for_configuration(period, date(2026, 9, 1))


def test_resolution_does_not_mutate_legacy_configuration():
    period = config(date(2026, 8, 15), duration=2, end=date(2026, 9, 30))
    before = (period.duration_months, period.effective_from, period.effective_to, period.status)
    FinancePeriodDefinition.resolved_for_configuration(period, date(2026, 9, 20))
    after = (period.duration_months, period.effective_from, period.effective_to, period.status)
    assert after == before
