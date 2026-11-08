from datetime import date

import pytest

from centermanager.services.monthly_tuition_plan import activate_monthly_plan, preview_monthly_plan
from centermanager.services.monthly_tuition_obligation import (
    MonthlySessionDecision, MonthlySessionOutcome,
    project_monthly_obligation, quarterly_prepayment_target,
)


def plan():
    return preview_monthly_plan(
        class_id=1, month=date(2026, 11, 1), monthly_fee_vnd=800_000,
        schedule_version="v1",
        session_dates=[date(2026, 11, i) for i in range(1, 10)],
    )


def test_requires_activation():
    with pytest.raises(ValueError):
        project_monthly_obligation(plan(), enrollment_effective_date=date(2026, 11, 1))


def test_cancellation_refunds_exact_allocation_without_redistribution():
    p = activate_monthly_plan(plan())
    result = project_monthly_obligation(
        p, enrollment_effective_date=date(2026, 11, 1),
        outcomes=[MonthlySessionDecision(
            date(2026, 11, 1), MonthlySessionOutcome.CENTRE_CANCELLED_NO_MAKEUP
        )],
    )
    assert result.gross_vnd == 800_000
    assert result.centre_cancellation_credit_vnd == 88_889
    assert result.net_due_vnd == 711_111


def test_midmonth_excludes_prior_cancellation():
    p = activate_monthly_plan(plan())
    result = project_monthly_obligation(
        p, enrollment_effective_date=date(2026, 11, 5),
        outcomes=[MonthlySessionDecision(
            date(2026, 11, 1), MonthlySessionOutcome.CENTRE_CANCELLED_NO_MAKEUP
        )],
    )
    assert result.centre_cancellation_credit_vnd == 0
    assert result.net_due_vnd == sum(a.amount_vnd for a in p.allocations[4:])


def test_reschedule_preserves_price():
    p = activate_monthly_plan(plan())
    result = project_monthly_obligation(
        p, enrollment_effective_date=date(2026, 11, 1),
        outcomes=[MonthlySessionDecision(
            date(2026, 11, 1), MonthlySessionOutcome.CENTRE_RESCHEDULED
        )],
    )
    assert result.net_due_vnd == 800_000


def test_duplicate_and_unknown_session_rejected():
    p = activate_monthly_plan(plan())
    decision = MonthlySessionDecision(date(2026, 11, 1), MonthlySessionOutcome.BILLABLE)
    with pytest.raises(ValueError):
        project_monthly_obligation(p, enrollment_effective_date=date(2026, 11, 1), outcomes=[decision, decision])
    with pytest.raises(ValueError):
        project_monthly_obligation(p, enrollment_effective_date=date(2026, 11, 1),
            outcomes=[MonthlySessionDecision(date(2026, 12, 1), MonthlySessionOutcome.BILLABLE)])


def test_quarterly_quote_is_sum_not_automatic_income():
    p = activate_monthly_plan(plan())
    due = project_monthly_obligation(p, enrollment_effective_date=date(2026, 11, 1))
    assert quarterly_prepayment_target([due, due, due]) == 2_400_000
    with pytest.raises(ValueError):
        quarterly_prepayment_target([due])
