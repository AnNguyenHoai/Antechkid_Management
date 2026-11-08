"""Future-only monthly Enrollment activation using repository-owned persistence."""
from __future__ import annotations

from datetime import date, datetime, timezone

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.repositories.provider import (
    RepositoryProvider, create_default_repository_provider,
)
from centermanager.services.recovery_change_outbox import (
    mirror_after_successful_commit, record_for_active_write,
)


class MonthlyEnrollmentActivationError(ValueError):
    pass


class MonthlyTuitionEnrollmentService:
    def __init__(self, session_factory, repository_provider: RepositoryProvider | None = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

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
            repo = self._repository_provider.monthly_tuition(db)
            enrollment = repo.enrollment(enrollment_id)
            if enrollment is None or enrollment.class_id is None:
                raise MonthlyEnrollmentActivationError("Enrollment not found")
            if enrollment.status != "ACTIVE" or getattr(enrollment, "reconciled_into_enrollment_id", None):
                raise MonthlyEnrollmentActivationError("Only canonical active Enrollment can switch")
            if not enrollment.has_tuition_contract:
                raise MonthlyEnrollmentActivationError("Historical tuition snapshot is unresolved")
            if repo.term(enrollment.id) is not None:
                raise MonthlyEnrollmentActivationError("Enrollment already opted into monthly tuition")
            if repo.unattributed_tuition_receipt(enrollment.student_id, enrollment.class_id):
                raise MonthlyEnrollmentActivationError(
                    "Unattributed historical Tuition payment must be reconciled first"
                )
            if repo.active_plan(enrollment.class_id, effective_from) is None:
                raise MonthlyEnrollmentActivationError(
                    "Active monthly plan for effective month is required"
                )
            term = repo.create_term(
                enrollment_id=enrollment.id, effective_from=effective_from,
                actor_name=actor_name,
                activated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            record_for_active_write(
                db, module="tuition", action="OPT_IN_MONTHLY",
                entity_type="EnrollmentMonthlyTuitionTerm", entity_id=term.id,
                summary_args={"enrollment_id": enrollment.id, "class_id": enrollment.class_id},
            )
            db.commit()
            mirror_after_successful_commit(db)
            return term.id
