"""Idempotent monthly session outcomes with repository-owned SQLAlchemy."""
from __future__ import annotations

from datetime import datetime, timezone

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.repositories.provider import (
    RepositoryProvider, create_default_repository_provider,
)
from centermanager.models.session import SessionStatus
from centermanager.services.monthly_tuition_ledger_projection import SessionBillingOutcome
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyOutcomeError(ValueError):
    pass


class MonthlyTuitionOutcomeService:
    def __init__(self, session_factory, repository_provider: RepositoryProvider | None = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

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
            repo = self._repository_provider.monthly_tuition(db)
            previous_command = repo.outcome_by_key(idempotency_key)
            if previous_command is not None:
                if (previous_command.enrollment_id != enrollment_id
                        or previous_command.session_id != session_id
                        or previous_command.outcome != outcome.value
                        or previous_command.reason != reason.strip()
                        or previous_command.replacement_session_id != replacement_session_id):
                    raise MonthlyOutcomeError("Idempotency key reused by a different command")
                return previous_command.id

            enrollment = repo.enrollment(enrollment_id)
            lesson = repo.teaching_session(session_id)
            if enrollment is None or lesson is None or enrollment.class_id != lesson.class_id:
                raise MonthlyOutcomeError("Session does not belong to Enrollment class")
            allocation = repo.active_allocation_for_session(
                enrollment.class_id, session_id,
            )
            if allocation is None:
                raise MonthlyOutcomeError("Session has no immutable activated monthly fee allocation")
            term = repo.term(enrollment_id)
            if (term is None or allocation.original_date < term.effective_from
                    or (term.effective_until is not None
                        and allocation.original_date > term.effective_until)):
                raise MonthlyOutcomeError("Session is not covered by activated monthly contract")
            if outcome == SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP:
                if lesson.status != SessionStatus.CANCELLED.value:
                    raise MonthlyOutcomeError("Only a cancelled center lesson can be waived")
            if replacement_session_id is not None:
                replacement = repo.teaching_session(replacement_session_id)
                if (replacement is None or replacement.id == lesson.id
                        or replacement.class_id != lesson.class_id):
                    raise MonthlyOutcomeError("Replacement must be a distinct lesson in same class")
                if repo.replacement_already_allocated(replacement_session_id):
                    raise MonthlyOutcomeError("Replacement is already part of a billed monthly plan")
            existing = repo.outcomes_for_session(enrollment_id, session_id)
            latest = max(existing, key=lambda row: row.revision, default=None)
            if latest is not None and latest.outcome == outcome.value:
                raise MonthlyOutcomeError("Outcome unchanged; retry with original idempotency key")
            event = repo.create_outcome(
                enrollment_id=enrollment_id, session_id=session_id,
                outcome=outcome.value, revision=(latest.revision + 1 if latest else 1),
                replacement_session_id=replacement_session_id,
                reason=reason.strip(), idempotency_key=idempotency_key.strip(),
                effective_date=get_clock().today(),
                recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
                recorded_by=actor_name,
            )
            record_for_active_write(
                db, module="tuition", action="SESSION_BILLING_OUTCOME",
                entity_type="MonthlyTuitionOutcome", entity_id=event.id,
                summary_args={"enrollment_id": enrollment_id, "session_id": session_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return event.id
