"""Pure monthly tuition obligation projection (Phase 3 integration boundary).

No SQLCipher mutation or Income posting occurs here. Legacy Enrollment tuition
remains authoritative until a persisted, explicitly activated monthly contract
is wired into the existing finance read/write services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Sequence

from centermanager.services.monthly_tuition_plan import MonthlyTuitionPlan, PlanStatus


class MonthlySessionOutcome(str, Enum):
    BILLABLE = "BILLABLE"
    CENTRE_CANCELLED_NO_MAKEUP = "CENTRE_CANCELLED_NO_MAKEUP"
    CENTRE_RESCHEDULED = "CENTRE_RESCHEDULED"


@dataclass(frozen=True)
class MonthlySessionDecision:
    session_date: date
    outcome: MonthlySessionOutcome


@dataclass(frozen=True)
class MonthlyObligation:
    gross_vnd: int
    centre_cancellation_credit_vnd: int
    net_due_vnd: int


def project_monthly_obligation(
    plan: MonthlyTuitionPlan,
    *,
    enrollment_effective_date: date,
    outcomes: Sequence[MonthlySessionDecision] = (),
) -> MonthlyObligation:
    """Compute tuition without double charging absences, makeup or reschedules.

    Centre cancellation credit is a reduction of accrued obligation, not a
    cash refund. The caller must choose a single posting strategy: waive
    charge *or* reverse an existing charge, never both.
    """
    if plan.status not in (PlanStatus.ACTIVE, PlanStatus.CLOSED):
        raise ValueError("only activated plans may produce obligations")
    if not isinstance(enrollment_effective_date, date):
        raise TypeError("enrollment_effective_date must be a date")
    amounts = {allocation.session_date: allocation.amount_vnd for allocation in plan.allocations}
    seen = set()
    for decision in outcomes:
        if decision.session_date not in amounts:
            raise ValueError("outcome does not belong to plan")
        if decision.session_date in seen:
            raise ValueError("duplicate outcome for planned session")
        if not isinstance(decision.outcome, MonthlySessionOutcome):
            raise ValueError("unsupported outcome")
        seen.add(decision.session_date)
    eligible = {day: amount for day, amount in amounts.items() if day >= enrollment_effective_date}
    gross = sum(eligible.values())
    credit = sum(
        eligible[decision.session_date]
        for decision in outcomes
        if decision.outcome == MonthlySessionOutcome.CENTRE_CANCELLED_NO_MAKEUP
        and decision.session_date in eligible
    )
    return MonthlyObligation(gross, credit, gross - credit)


def quarterly_prepayment_target(monthly_obligations: Sequence[MonthlyObligation]) -> int:
    """Quote three monthly obligations; this is not realized tuition income."""
    if len(monthly_obligations) != 3:
        raise ValueError("quarterly quote requires exactly three months")
    return sum(item.net_due_vnd for item in monthly_obligations)
