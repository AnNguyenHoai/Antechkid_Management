"""Single-transaction center cancellation decision for a whole monthly class.

The class session must already be CANCELLED. The cancellation decision is
applied to all eligible opted-in enrollments or none, with immutable,
versioned outcome evidence. It never creates an Income transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.models.enrollment import Enrollment
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionPlanRecord,
    MonthlyTuitionAllocationRecord, MonthlyTuitionOutcomeRecord,
)
from centermanager.models.session import Session, SessionStatus
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyClassCancellationError(ValueError):
    pass


class MonthlyTuitionClassCancellationService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @require_permission("finance.income.create")
    def approve_no_makeup(self, class_id: int, session_id: int, *, reason: str) -> int:
        """One durable cancellation for every eligible monthly Enrollment."""
        if not reason or not reason.strip() or len(reason.strip()) > 255:
            raise MonthlyClassCancellationError("A concise cancellation reason is required")
        actor = get_current_user()
        actor_name = getattr(actor, "username", None)
        if not actor_name:
            raise MonthlyClassCancellationError("Authenticated finance actor is required")
        with self._session_factory() as db:
            lesson = db.get(Session, session_id)
            if lesson is None or lesson.class_id != class_id:
                raise MonthlyClassCancellationError("Session/class identity mismatch")
            if lesson.status != SessionStatus.CANCELLED.value:
                raise MonthlyClassCancellationError("Lesson must be cancelled first")
            plan = db.scalars(select(MonthlyTuitionPlanRecord).where(
                MonthlyTuitionPlanRecord.class_id == class_id,
                MonthlyTuitionPlanRecord.month == lesson.scheduled_date.replace(day=1),
                MonthlyTuitionPlanRecord.status.in_(("ACTIVE", "CLOSED")),
            )).first()
            if plan is None:
                raise MonthlyClassCancellationError("No activated tuition plan for this class/month")
            allocation = db.scalars(select(MonthlyTuitionAllocationRecord).where(
                MonthlyTuitionAllocationRecord.plan_id == plan.id,
                MonthlyTuitionAllocationRecord.session_id == session_id,
            )).first()
            if allocation is None:
                raise MonthlyClassCancellationError("Lesson has no original monthly allocation")
            # Iterate exact Enrollment contracts, never net across students/classes.
            terms = db.scalars(select(EnrollmentMonthlyTuitionTerm).join(
                Enrollment, Enrollment.id == EnrollmentMonthlyTuitionTerm.enrollment_id
            ).where(Enrollment.class_id == class_id)).all()
            count = 0
            for term in terms:
                enrollment = db.get(Enrollment, term.enrollment_id)
                if (term.effective_from > lesson.scheduled_date
                        or (term.effective_until is not None and lesson.scheduled_date > term.effective_until)
                        or (enrollment.start_date is not None and lesson.scheduled_date < enrollment.start_date)
                        or (enrollment.end_date is not None and lesson.scheduled_date > enrollment.end_date)
                        or (enrollment.withdrawn_from_session is not None
                            and lesson.session_number >= enrollment.withdrawn_from_session)):
                    continue
                previous = db.scalars(select(MonthlyTuitionOutcomeRecord).where(
                    MonthlyTuitionOutcomeRecord.enrollment_id == enrollment.id,
                    MonthlyTuitionOutcomeRecord.session_id == lesson.id,
                )).all()
                latest = max(previous, key=lambda x: x.revision, default=None)
                if latest is not None and latest.outcome == "CENTRE_CANCELLED_NO_MAKEUP":
                    continue  # deterministic retry / no second wallet credit
                revision = latest.revision + 1 if latest is not None else 1
                event = MonthlyTuitionOutcomeRecord(
                    enrollment_id=enrollment.id, session_id=lesson.id,
                    revision=revision, outcome="CENTRE_CANCELLED_NO_MAKEUP",
                    replacement_session_id=None,
                    reason=reason.strip(),
                    idempotency_key=f"monthly-cancel:{class_id}:{session_id}:{enrollment.id}:{revision}",
                    effective_date=get_clock().today(),
                    recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    recorded_by=actor_name,
                )
                db.add(event)
                count += 1
            if not count:
                return 0
            db.flush()
            record_for_active_write(
                db, module="tuition", action="CANCEL_CLASS_MONTHLY",
                entity_type="MonthlyTuitionOutcome", entity_id=session_id,
                summary_args={"class_id": class_id, "session_id": session_id,
                              "record_count": count},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return count
