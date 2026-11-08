"""Read-only monthly tuition plan preview and explicit state transitions.

No persistence, legacy accrual switching, or wallet side effects in this phase.
The application service must enforce permissions and concurrency when storing
activated plans.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Sequence

from centermanager.services.monthly_tuition_calculator import (
    MonthlySessionAllocation,
    allocate_monthly_tuition,
)


class PlanStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class MonthlyTuitionPlan:
    class_id: int
    month: date
    monthly_fee_vnd: int
    schedule_version: str
    version: int
    allocations: tuple[MonthlySessionAllocation, ...]
    status: PlanStatus = PlanStatus.DRAFT


def preview_monthly_plan(
    *,
    class_id: int,
    month: date,
    monthly_fee_vnd: int,
    schedule_version: str,
    session_dates: Sequence[date],
    version: int = 1,
) -> MonthlyTuitionPlan:
    if class_id <= 0 or version <= 0:
        raise ValueError("class_id and version must be positive")
    if month.day != 1:
        raise ValueError("month must be the first day of a calendar month")
    if not schedule_version.strip():
        raise ValueError("schedule_version must not be empty")
    allocations = allocate_monthly_tuition(monthly_fee_vnd, session_dates)
    if allocations[0].session_date.year != month.year or allocations[0].session_date.month != month.month:
        raise ValueError("session dates must match the requested plan month")
    return MonthlyTuitionPlan(
        class_id, month, monthly_fee_vnd, schedule_version, version, allocations
    )


def activate_monthly_plan(plan: MonthlyTuitionPlan) -> MonthlyTuitionPlan:
    if plan.status != PlanStatus.DRAFT:
        raise ValueError("only draft plans can be activated")
    return replace(plan, status=PlanStatus.ACTIVE)


def close_monthly_plan(plan: MonthlyTuitionPlan) -> MonthlyTuitionPlan:
    if plan.status != PlanStatus.ACTIVE:
        raise ValueError("only active plans can be closed")
    return replace(plan, status=PlanStatus.CLOSED)


def revise_draft(
    plan: MonthlyTuitionPlan, *, session_dates: Sequence[date],
    monthly_fee_vnd: int | None = None, schedule_version: str | None = None,
) -> MonthlyTuitionPlan:
    if plan.status != PlanStatus.DRAFT:
        raise ValueError("activated allocations are immutable; create an explicit adjustment")
    return preview_monthly_plan(
        class_id=plan.class_id, month=plan.month,
        monthly_fee_vnd=plan.monthly_fee_vnd if monthly_fee_vnd is None else monthly_fee_vnd,
        schedule_version=plan.schedule_version if schedule_version is None else schedule_version,
        session_dates=session_dates, version=plan.version + 1,
    )
