"""Authorized storage of opt-in monthly tuition *plans* only.

This is an internal persistence seam, not a production feature switch. Legacy
accrual and finance readers are unchanged until policy routing is implemented.
All mutations obey the existing SQLCipher WRITE gate and recovery outbox.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable

from sqlalchemy import select

from centermanager.core.permission_guard import require_permission
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.class_ import Class
from centermanager.models.monthly_tuition import (
    MonthlyTuitionAllocationRecord, MonthlyTuitionPlanRecord,
    MonthlyClassDefaultRecord,
)
from centermanager.models.session import Session, SessionStatus
from centermanager.models.enrollment import Enrollment
from centermanager.models.income import Income
from centermanager.models.attendance import Attendance
from centermanager.services.monthly_tuition_ledger_projection import allocate_by_session_id
from centermanager.services.monthly_class_schedule_service import month_dates
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyPlanStorageError(ValueError):
    pass


class MonthlyTuitionPlanStore:
    """Persistence facade: no external callers should bypass this service."""

    def __init__(self, session_factory: Callable):
        self._session_factory = session_factory

    @staticmethod
    def _candidate_sessions(db, class_id: int, month: date):
        if type(class_id) is not int or class_id <= 0:
            raise MonthlyPlanStorageError("class_id must be positive")
        if type(month) is not date or month.day != 1:
            raise MonthlyPlanStorageError("month must be a calendar-month start")
        sessions = db.scalars(
            select(Session).where(Session.class_id == class_id)
        ).all()
        return [(row.id, row.scheduled_date) for row in sessions
                if row.scheduled_date.year == month.year
                and row.scheduled_date.month == month.month]

    @staticmethod
    def _assert_complete_month(db, class_id: int, month: date) -> None:
        policy = db.get(MonthlyClassDefaultRecord, class_id)
        if policy is None:  # Existing legacy opt-in remains unchanged.
            return
        klass = db.get(Class, class_id)
        if not policy.weekly_days or klass.start_date is None:
            raise MonthlyPlanStorageError(
                "Monthly class has no weekly schedule. Generate the month sessions first."
            )
        weekdays = tuple(int(day) for day in policy.weekly_days.split(","))
        expected = month_dates(klass.start_date, klass.end_date, month, weekdays)
        actual = [day for _, day in MonthlyTuitionPlanStore._candidate_sessions(db, class_id, month)]
        if not expected or sorted(actual) != list(expected):
            raise MonthlyPlanStorageError(
                "Monthly sessions do not match the configured weekly timetable. "
                "Generate/reconcile the full schedule before activating tuition."
            )

    @staticmethod
    def _active_class(db, class_id: int):
        class_record = db.get(Class, class_id)
        if class_record is None:
            raise MonthlyPlanStorageError("Class not found")
        if class_record.deleted_at is not None or class_record.status != "ACTIVE":
            raise MonthlyPlanStorageError("Archived or inactive class cannot change tuition plan")

    def preview(self, class_id: int, month: date, fee_vnd: int):
        with self._session_factory() as db:
            self._active_class(db, class_id)
            self._assert_complete_month(db, class_id, month)
            return allocate_by_session_id(
                fee_vnd, self._candidate_sessions(db, class_id, month)
            )

    @require_permission("class.update")
    def create_draft(self, class_id: int, month: date, fee_vnd: int,
                     schedule_version: str) -> int:
        if not isinstance(schedule_version, str) or not schedule_version.strip():
            raise MonthlyPlanStorageError("schedule_version is required")
        with self._session_factory() as db:
            self._active_class(db, class_id)
            self._assert_complete_month(db, class_id, month)
            default = db.get(MonthlyClassDefaultRecord, class_id)
            if default is not None:
                if month < default.effective_month or fee_vnd != default.monthly_fee_vnd:
                    raise MonthlyPlanStorageError(
                        "Monthly plan must match the class billing policy and effective period."
                    )
            allocations = allocate_by_session_id(
                fee_vnd, self._candidate_sessions(db, class_id, month)
            )
            existing = db.scalars(
                select(MonthlyTuitionPlanRecord).where(
                    MonthlyTuitionPlanRecord.class_id == class_id,
                    MonthlyTuitionPlanRecord.month == month,
                )
            ).all()
            if any(row.status in ("ACTIVE", "CLOSED") for row in existing):
                raise MonthlyPlanStorageError("Activated plan exists; do not reprice history")
            version = max((int(row.version) for row in existing), default=0) + 1
            plan = MonthlyTuitionPlanRecord(
                class_id=class_id, month=month, version=version,
                monthly_fee_vnd=fee_vnd, schedule_version=schedule_version.strip(),
                status="DRAFT",
            )
            db.add(plan)
            db.flush()
            db.add_all([
                MonthlyTuitionAllocationRecord(
                    plan_id=plan.id, session_id=item.session_id,
                    original_date=item.scheduled_date, amount_vnd=item.amount_vnd,
                ) for item in allocations
            ])
            record_for_active_write(
                db, module="tuition", action="CREATE_MONTHLY_PLAN",
                entity_type="MonthlyTuitionPlan", entity_id=plan.id,
                summary_args={"class_id": class_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return plan.id

    @require_permission("class.update")
    def activate(self, plan_id: int) -> None:
        current_actor = get_current_user()
        actor = getattr(current_actor, "username", None)
        if not actor:
            raise MonthlyPlanStorageError("authenticated actor is required")
        with self._session_factory() as db:
            plan = db.get(MonthlyTuitionPlanRecord, plan_id)
            if plan is None or plan.status != "DRAFT":
                raise MonthlyPlanStorageError("only an existing draft may activate")
            self._active_class(db, plan.class_id)
            self._assert_complete_month(db, plan.class_id, plan.month)
            today = get_clock().today()
            if (plan.month.year, plan.month.month) <= (today.year, today.month):
                default = db.get(MonthlyClassDefaultRecord, plan.class_id)
                # The only exception is an *initial current-month* monthly
                # bootstrap on an entirely unused business database. Never
                # let this path reprice a legacy enrollment or collected cash.
                is_current = (plan.month.year, plan.month.month) == (today.year, today.month)
                initial_month = (
                    default is not None and default.effective_month == plan.month
                    and default.created_at.date().replace(day=1) == plan.month
                )
                any_cash = db.query(Income.id).first() is not None
                any_contract = db.query(Enrollment.id).first() is not None
                any_completed = db.query(Session.id).filter(
                    Session.status != SessionStatus.SCHEDULED.value
                ).first() is not None
                any_attendance = db.query(Attendance.id).first() is not None
                if not (
                    is_current and initial_month and not any_cash
                    and not any_contract and not any_completed and not any_attendance
                ):
                    raise MonthlyPlanStorageError(
                        "Current/past month activation is restricted to an unused "
                        "new monthly database in its first billing month."
                    )
            other_active = db.scalars(
                select(MonthlyTuitionPlanRecord).where(
                    MonthlyTuitionPlanRecord.class_id == plan.class_id,
                    MonthlyTuitionPlanRecord.month == plan.month,
                    MonthlyTuitionPlanRecord.status == "ACTIVE",
                )
            ).all()
            if other_active:
                raise MonthlyPlanStorageError("one active plan per class/month")
            allocations = db.scalars(
                select(MonthlyTuitionAllocationRecord).where(
                    MonthlyTuitionAllocationRecord.plan_id == plan.id
                )
            ).all()
            if not allocations or sum(row.amount_vnd for row in allocations) != plan.monthly_fee_vnd:
                raise MonthlyPlanStorageError("plan allocation total is invalid")
            sessions = {row.id: row for row in db.scalars(
                select(Session).where(Session.class_id == plan.class_id)
            ).all()}
            candidate_ids = {sid for sid, _ in self._candidate_sessions(db, plan.class_id, plan.month)}
            if {row.session_id for row in allocations} != candidate_ids:
                raise MonthlyPlanStorageError("planned sessions changed; recreate draft")
            if any(row.session_id not in sessions
                   or sessions[row.session_id].scheduled_date != row.original_date
                   or (row.original_date.year, row.original_date.month)
                   != (plan.month.year, plan.month.month)
                   for row in allocations):
                raise MonthlyPlanStorageError("schedule changed since draft; recreate plan")
            plan.status = "ACTIVE"
            plan.activated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            plan.activated_by = actor.strip()
            record_for_active_write(
                db, module="tuition", action="ACTIVATE_MONTHLY_PLAN",
                entity_type="MonthlyTuitionPlan", entity_id=plan.id,
                summary_args={"class_id": plan.class_id},
            )
            db.commit()
            mirror_after_successful_commit(db)

    @require_permission("class.update")
    def close(self, plan_id: int) -> None:
        """Close a completed month while retaining immutable fee allocations."""
        with self._session_factory() as db:
            plan = db.get(MonthlyTuitionPlanRecord, plan_id)
            if plan is None or plan.status != "ACTIVE":
                raise MonthlyPlanStorageError("Only an active plan can be closed")
            today = get_clock().today()
            if (plan.month.year, plan.month.month) >= (today.year, today.month):
                raise MonthlyPlanStorageError("Current and future months cannot be closed")
            plan.status = "CLOSED"
            record_for_active_write(
                db, module="tuition", action="CLOSE_MONTHLY_PLAN",
                entity_type="MonthlyTuitionPlan", entity_id=plan.id,
                summary_args={"class_id": plan.class_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
