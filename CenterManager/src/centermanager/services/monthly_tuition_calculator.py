"""Pure, deterministic VND monthly tuition allocation.

This module does not alter the legacy Enrollment tuition snapshot, accrual,
attendance, accounting period, or wallet. Consumers must explicitly opt in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Sequence


@dataclass(frozen=True)
class MonthlySessionAllocation:
    session_date: date
    amount_vnd: int


def allocate_monthly_tuition(
    monthly_fee_vnd: int,
    session_dates: Sequence[date],
) -> tuple[MonthlySessionAllocation, ...]:
    """Allocate an integer VND fee over distinct, chronological planned dates.

    Session dates are unique in V1; two sessions on one date require a stable
    session identifier in a future interface, not an ambiguous date-only key.
    """
    if isinstance(monthly_fee_vnd, bool) or not isinstance(monthly_fee_vnd, int):
        raise TypeError("monthly_fee_vnd must be an integer number of VND")
    if monthly_fee_vnd < 0:
        raise ValueError("monthly_fee_vnd must be nonnegative")
    dates = tuple(session_dates)
    if not dates:
        raise ValueError("monthly tuition requires at least one planned session")
    if any(not isinstance(day, date) or isinstance(day, __import__("datetime").datetime) for day in dates):
        raise TypeError("session_dates must contain date values")
    if len(set(dates)) != len(dates):
        raise ValueError("duplicate session dates are not supported")
    if len({(day.year, day.month) for day in dates}) != 1:
        raise ValueError("all planned sessions must belong to one calendar month")
    ordered = sorted(dates)
    quotient, remainder = divmod(monthly_fee_vnd, len(ordered))
    return tuple(
        MonthlySessionAllocation(day, quotient + (index < remainder))
        for index, day in enumerate(ordered)
    )


def tuition_due_from(
    allocations: Sequence[MonthlySessionAllocation], effective_date: date
) -> int:
    """Mid-month enrolment: sum only planned sessions on/after start date."""
    if not isinstance(effective_date, date):
        raise TypeError("effective_date must be a date")
    return sum(item.amount_vnd for item in allocations if item.session_date >= effective_date)


def cancellation_credit(
    allocations: Sequence[MonthlySessionAllocation], cancelled_date: date
) -> int:
    """Value of one cancelled session; caller controls idempotent posting."""
    matches = [item.amount_vnd for item in allocations if item.session_date == cancelled_date]
    if len(matches) != 1:
        raise ValueError("cancelled session must match exactly one allocation")
    return matches[0]
