"""Immutable, idempotent monthly teaching-session billing outcome commands.

No Income rows are created by cancellation. Opt-in monthly accrual reduces the
obligation exactly once; real cash refunds remain TuitionAdjustmentService work.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.models.enrollment import Enrollment
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionAllocationRecord,
    MonthlyTuitionOutcomeRecord, MonthlyTuitionPlanRecord,
)
from centermanager.models.session import Session, SessionStatus
from centermanager.services.monthly_tuition_ledger_projection import SessionBillingOutcome
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyOutcomeError(ValueError):
    pass


class MonthlyTuitionOutcomeService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @require_permission("finance.income.create")
    def record_outcome(
        self, enrollment_id: int, session_id: int, outcome: SessionBillingOutcome,
        *, reason: str, idempotency_key: str, replacement_session_id: int | None = None,
    ) -> int:
        if not isinstance(outcome, SessionBillingOutcome):
            raise MonthlyOutcomeError("Unsupported billing outcome")
        if not reason or not reason.strip() or not idempotency_key or not idempotency_key.strip():
            raise MonthlyOutcomeError("Reason and idempotency key are mandatory")
        if len(reason) > 255 or len(idempotency_key) > 120:
            raise MonthlyOutcomeError("Reason or idempotency key too long")
        if (outcome == SessionBillingOutcome.RESCHEDULED) != (replacement_session_id is not None):
            raise MonthlyOutcomeError("Rescheduled lesson requires one replacement session")
        actor = get_current_user()
        actor_name = getattr(actor, "username", None)
        if not actor_name:
            raise MonthlyOutcomeError("Authenticated finance actor required")
        with self._session_factory() as db:
            previous_command = db.scalars(select(MonthlyTuitionOutcomeRecord).where(
                MonthlyTuitionOutcomeRecord.idempotency_key == idempotency_key
            )).first()
            if previous_command is not None:
                if (previous_command.enrollment_id != enrollment_id
                        or previous_command.session_id != session_id
                        or previous_command.outcome != outcome.value
                        or previous_command.reason != reason.strip()
                        or previous_command.replacement_session_id != replacement_session_id):
                    raise MonthlyOutcomeError("Idempotency key reused by a different command")
                return previous_command.id

            enrollment = db.get(Enrollment, enrollment_id)
            lesson = db.get(Session, session_id)
            if enrollment is None or lesson is None or enrollment.class_id != lesson.class_id:
                raise MonthlyOutcomeError("Session does not belong to Enrollment class")
            term = db.scalars(select(EnrollmentMonthlyTuitionTerm).where(
                EnrollmentMonthlyTuitionTerm.enrollment_id == enrollment_id
            )).first()
            if term is None or lesson.scheduled_date < term.effective_from:
                raise MonthlyOutcomeError("Session is not covered by activated monthly contract")
            plan = db.scalars(select(MonthlyTuitionPlanRecord).where(
                MonthlyTuitionPlanRecord.class_id == enrollment.class_id,
                MonthlyTuitionPlanRecord.month == lesson.scheduled_date.replace(day=1),
                MonthlyTuitionPlanRecord.status.in_(("ACTIVE", "CLOSED")),
            )).first()
            if plan is None:
                raise MonthlyOutcomeError("No activated monthly tuition plan for this lesson")
            allocation = db.scalars(select(MonthlyTuitionAllocationRecord).where(
                MonthlyTuitionAllocationRecord.plan_id == plan.id,
                MonthlyTuitionAllocationRecord.session_id == session_id,
            )).first()
            if allocation is None:
                raise MonthlyOutcomeError("Session has no immutable monthly fee allocation")
            if outcome == SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP:
                if lesson.status != SessionStatus.CANCELLED.value:
                    raise MonthlyOutcomeError("Only a cancelled center lesson can be waived")
            if replacement_session_id is not None:
                replacement = db.get(Session, replacement_session_id)
                if (replacement is None or replacement.id == lesson.id
                        or replacement.class_id != lesson.class_id):
                    raise MonthlyOutcomeError("Replacement must be a distinct lesson in same class")
                already_billable = db.scalars(select(MonthlyTuitionAllocationRecord).where(
                    MonthlyTuitionAllocationRecord.session_id == replacement_session_id
                )).first()
                if already_billable is not None:
                    raise MonthlyOutcomeError("Replacement is already part of a billed monthly plan")
            existing = db.scalars(select(MonthlyTuitionOutcomeRecord).where(
                MonthlyTuitionOutcomeRecord.enrollment_id == enrollment_id,
                MonthlyTuitionOutcomeRecord.session_id == session_id,
            )).all()
            latest = max(existing, key=lambda row: row.revision, default=None)
            if latest is not None and latest.outcome == outcome.value:
                raise MonthlyOutcomeError("Outcome unchanged; retry with original idempotency key")
            event = MonthlyTuitionOutcomeRecord(
                enrollment_id=enrollment_id, session_id=session_id,
                outcome=outcome.value, revision=(latest.revision + 1 if latest else 1),
                replacement_session_id=replacement_session_id,
                reason=reason.strip(), idempotency_key=idempotency_key.strip(),
                effective_date=get_clock().today(),
                recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
                recorded_by=actor_name,
            )
            db.add(event)
            db.flush()
            record_for_active_write(
                db, module="tuition", action="SESSION_BILLING_OUTCOME",
                entity_type="MonthlyTuitionOutcome", entity_id=event.id,
                summary_args={"enrollment_id": enrollment_id, "session_id": session_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return event.id
