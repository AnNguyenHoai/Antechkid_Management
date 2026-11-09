"""Immutable session-identity tuition ledger projection.

Deliberately pure: database writes and Income cash movements must be handled by
the authoritative Finance/WRITE services, never by a read model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Iterable


class SessionBillingOutcome(str, Enum):
    BILLABLE = "BILLABLE"  # includes student absence; makeup is not another charge
    RESCHEDULED = "RESCHEDULED"
    CENTRE_CANCELLED_NO_MAKEUP = "CENTRE_CANCELLED_NO_MAKEUP"


@dataclass(frozen=True)
class AllocatedSession:
    session_id: int
    scheduled_date: date
    amount_vnd: int


@dataclass(frozen=True)
class SessionBillingEvent:
    session_id: int
    outcome: SessionBillingOutcome
    revision: int = 1


@dataclass(frozen=True)
class EnrollmentMonthlyBalance:
    enrollment_id: int
    gross_vnd: int
    cancelled_vnd: int
    earned_vnd: int
    cash_received_vnd: int
    outstanding_vnd: int
    prepaid_vnd: int


def allocate_by_session_id(
    monthly_fee_vnd: int, sessions: Iterable[tuple[int, date]],
) -> tuple[AllocatedSession, ...]:
    """Deterministic integer allocation across real Session IDs, including same-day lessons."""
    if type(monthly_fee_vnd) is not int or monthly_fee_vnd < 0:
        raise ValueError("monthly_fee_vnd must be nonnegative integer VND")
    items = list(sessions)
    if not items:
        raise ValueError("a monthly plan requires at least one session")
    if any(type(sid) is not int or sid <= 0 or type(day) is not date for sid, day in items):
        raise ValueError("session ID and scheduled date must be valid")
    if len({sid for sid, _ in items}) != len(items):
        raise ValueError("session ID is duplicated")
    if len({(d.year, d.month) for _, d in items}) != 1:
        raise ValueError("all sessions must belong to the same calendar month")
    ordered = sorted(items, key=lambda item: (item[1], item[0]))
    base, remainder = divmod(monthly_fee_vnd, len(ordered))
    return tuple(
        AllocatedSession(sid, day, base + (idx < remainder))
        for idx, (sid, day) in enumerate(ordered)
    )


def project_enrollment_month(
    *,
    enrollment_id: int,
    effective_from: date,
    as_of_date: date,
    allocations: Iterable[AllocatedSession],
    events: Iterable[SessionBillingEvent] = (),
    cash_received_vnd: int = 0,
    effective_until: date | None = None,
) -> EnrollmentMonthlyBalance:
    """Accrual as-of original planned date, not on the prepayment receipt date.

    Events are a resolved snapshot of latest authorised outcomes, not additive
    credits: this prevents duplicate cancellation adjustments in the projection.
    A real reversal must be persisted exactly once by the integration layer.
    """
    if type(enrollment_id) is not int or enrollment_id <= 0:
        raise ValueError("enrollment_id must be positive")
    if type(cash_received_vnd) is not int or cash_received_vnd < 0:
        raise ValueError("cash_received_vnd must be nonnegative integer")
    if type(effective_from) is not date or type(as_of_date) is not date:
        raise ValueError("effective_from/as_of_date must be dates")
    if effective_until is not None and (type(effective_until) is not date or effective_until < effective_from):
        raise ValueError("invalid enrollment end date")
    rows = tuple(allocations)
    by_id = {row.session_id: row for row in rows}
    if len(by_id) != len(rows) or any(
        type(row.session_id) is not int or row.session_id <= 0
        or type(row.scheduled_date) is not date or type(row.amount_vnd) is not int
        or row.amount_vnd < 0 for row in rows
    ):
        raise ValueError("invalid or duplicated immutable allocations")
    outcome_by_id = {}
    for event in events:
        if event.session_id not in by_id or event.session_id in outcome_by_id:
            raise ValueError("unknown or duplicate session outcome")
        if not isinstance(event.outcome, SessionBillingOutcome) or event.revision < 1:
            raise ValueError("invalid billing outcome")
        outcome_by_id[event.session_id] = event.outcome
    billable = tuple(row for row in rows if
        effective_from <= row.scheduled_date <= as_of_date
        and (effective_until is None or row.scheduled_date <= effective_until))
    gross = sum(row.amount_vnd for row in billable)
    cancelled = sum(row.amount_vnd for row in billable if
        outcome_by_id.get(row.session_id) == SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP)
    earned = gross - cancelled
    signed = earned - cash_received_vnd
    return EnrollmentMonthlyBalance(
        enrollment_id, gross, cancelled, earned, cash_received_vnd,
        max(0, signed), max(0, -signed),
    )
