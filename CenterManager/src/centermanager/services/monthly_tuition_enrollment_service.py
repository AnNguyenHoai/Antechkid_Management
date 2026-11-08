"""Opt-in switching of a single Enrollment to future monthly tuition.

An authorised manager must complete production backup/UAT preflight *before*
calling this internal command. It never modifies the original Enrollment
snapshot, historical Income or tuition adjustments.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.models.enrollment import Enrollment
from centermanager.models.income import Income
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionPlanRecord,
)
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyEnrollmentActivationError(ValueError):
    pass


class MonthlyTuitionEnrollmentService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @require_permission("tuition.enrollment.override")
    def activate_future_month(self, enrollment_id: int, effective_from: date) -> int:
        actor = get_current_user()
        actor_name = getattr(actor, "username", None)
        if not actor_name:
            raise MonthlyEnrollmentActivationError("Authenticated manager required")
        today = get_clock().today()
        if (type(effective_from) is not date or effective_from.day != 1
                or (effective_from.year, effective_from.month) <= (today.year, today.month)):
            raise MonthlyEnrollmentActivationError("Activation requires a future month start")
        with self._session_factory() as db:
            enrollment = db.get(Enrollment, enrollment_id)
            if enrollment is None or enrollment.class_id is None:
                raise MonthlyEnrollmentActivationError("Enrollment not found")
            if enrollment.status != "ACTIVE" or getattr(enrollment, "reconciled_into_enrollment_id", None):
                raise MonthlyEnrollmentActivationError("Only canonical active Enrollment can switch")
            if not enrollment.has_tuition_contract:
                raise MonthlyEnrollmentActivationError("Historical tuition snapshot is unresolved")
            if db.scalars(select(EnrollmentMonthlyTuitionTerm).where(
                EnrollmentMonthlyTuitionTerm.enrollment_id == enrollment.id
            )).first() is not None:
                raise MonthlyEnrollmentActivationError("Enrollment already opted into monthly tuition")
            unmatched_receipt = db.scalars(select(Income.id).where(
                Income.student_id == enrollment.student_id,
                Income.class_id == enrollment.class_id,
                Income.income_type == "Tuition",
                Income.enrollment_id.is_(None),
                Income.status == Income.STATUS_ACTIVE,
                Income.deleted_at.is_(None),
            )).first()
            if unmatched_receipt is not None:
                raise MonthlyEnrollmentActivationError(
                    "Unattributed historical Tuition payment must be reconciled first"
                )
            plan = db.scalars(select(MonthlyTuitionPlanRecord).where(
                MonthlyTuitionPlanRecord.class_id == enrollment.class_id,
                MonthlyTuitionPlanRecord.month == effective_from,
                MonthlyTuitionPlanRecord.status == "ACTIVE",
            )).first()
            if plan is None:
                raise MonthlyEnrollmentActivationError(
                    "Active monthly plan for effective month is required"
                )
            term = EnrollmentMonthlyTuitionTerm(
                enrollment_id=enrollment.id, effective_from=effective_from,
                activated_at=datetime.now(timezone.utc).replace(tzinfo=None),
                activated_by=actor_name,
            )
            db.add(term)
            db.flush()
            record_for_active_write(
                db, module="tuition", action="OPT_IN_MONTHLY",
                entity_type="EnrollmentMonthlyTuitionTerm", entity_id=term.id,
                summary_args={"enrollment_id": enrollment.id, "class_id": enrollment.class_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return term.id
