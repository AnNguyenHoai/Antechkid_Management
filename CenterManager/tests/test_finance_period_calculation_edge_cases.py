from datetime import date

from centermanager.models.finance_period import FinancePeriodDefinition


def test_period_for_date_handles_month_end_anchor():
    anchor = date(2026, 1, 31)
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 2, 28), 1) == (
        date(2026, 1, 31),
        date(2026, 2, 27),
    )


def test_period_for_date_handles_date_before_anchor():
    anchor = date(2026, 9, 1)
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 8, 31), 1) == (
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
