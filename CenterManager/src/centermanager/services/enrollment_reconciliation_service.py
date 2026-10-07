# -*- coding: utf-8 -*-
"""Safe reconciliation for legacy duplicate Enrollment contracts."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Tuple

from centermanager.core.capabilities import Capability
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.events.student_events import StudentEnrollmentChanged
from centermanager.repositories.provider import RepositoryProvider
from centermanager.services.audit_service import AuditService
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.enrollment_service import EnrollmentService, EnrollmentStatus


class EnrollmentReconciliationError(Exception):
    pass


class EnrollmentReconciliationValidationError(EnrollmentReconciliationError):
    pass


@dataclass(frozen=True)
class EnrollmentReconciliationCandidate:
    student_id: int
    student_name: str
    class_id: int
    class_name: str
    canonical_enrollment_id: int
    duplicate_enrollment_id: int
    canonical_range: Tuple[int, int]
    duplicate_effective_range: Tuple[int, int]
    tuition_income_count: int
    tuition_income_total: Decimal
    blockers: Tuple[str, ...]


class EnrollmentReconciliationService:
    """Repair accidental legacy remove/add duplicate contracts without deleting history."""

    def __init__(
        self,
        session_factory,
        repository_provider: RepositoryProvider,
        *,
        audit_service: Optional[AuditService] = None,
        event_bus=None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=repository_provider
        )
        self._event_bus = event_bus

    @classmethod
    def from_enrollment_service(cls, enrollment_service):
        return cls(
            enrollment_service._session_factory,
            enrollment_service._repository_provider,
            audit_service=enrollment_service._audit_service,
            event_bus=getattr(enrollment_service, "_event_bus", None),
        )

    @staticmethod
    def _require_reason(reason: str) -> str:
        resolved = (reason or "").strip()
        if not resolved:
            raise EnrollmentReconciliationValidationError(
                "A reconciliation reason is required."
            )
        return resolved

    @staticmethod
    def _require_actor(actor):
        resolved = actor if actor is not None else get_current_user()
        if resolved is not None:
            AuthorizationService.require(
                resolved, Capability.TUITION_ENROLLMENT_OVERRIDE
            )
        return resolved

    def _blockers(self, session, enrollment_id: int) -> Tuple[str, ...]:
        blockers = []
        if self._repository_provider.enrollment_freezes(session).list_for_enrollment(
            enrollment_id
        ):
            blockers.append("TUITION_FREEZE_HISTORY")
        if self._repository_provider.tuition_adjustments(session).has_for_enrollment(
            enrollment_id
        ):
            blockers.append("TUITION_ADJUSTMENT_LEDGER")
        if self._repository_provider.enrollment_transfers(session).has_for_enrollment(
            enrollment_id
        ):
            blockers.append("ENROLLMENT_TRANSFER_LEDGER")
        return tuple(blockers)

    @staticmethod
    def _income_summary(rows) -> tuple[int, Decimal]:
        total = Decimal("0")
        for row in rows:
            if getattr(row, "status", None) == "ACTIVE" and getattr(row, "deleted_at", None) is None:
                total += Decimal(str(getattr(row, "amount", 0) or 0))
        return len(rows), total

    @staticmethod
    def _canonical_range(enrollment) -> Optional[Tuple[int, int]]:
        start = getattr(enrollment, "enrolled_from_session", None)
        end = getattr(enrollment, "enrolled_until_session", None)
        if start is None or end is None:
            return None
        return int(start), int(end)

    @classmethod
    def _canonical_covers(
        cls,
        canonical,
        duplicate_range: Tuple[int, int],
    ) -> bool:
        canonical_range = cls._canonical_range(canonical)
        if canonical_range is None:
            return False
        return (
            canonical_range[0] <= duplicate_range[0]
            and canonical_range[1] >= duplicate_range[1]
        )

    def find_candidates(self, class_id: int) -> list[EnrollmentReconciliationCandidate]:
        """Find conservative legacy candidates for one class.

        Only WITHDRAWN contracts fully covered by the current ACTIVE contract are
        suggested. COMPLETED/non-covered histories remain untouched.
        """
        with self._session_factory() as session:
            repo = self._repository_provider.enrollments(session)
            rows = repo.get_by_class_with_student_including_reconciled(class_id)
            sessions = self._repository_provider.sessions(session).get_by_class(class_id)
            active_by_student = {
                item.student_id: item
                for item in rows
                if item.status == EnrollmentStatus.ACTIVE.value
                and item.reconciled_into_enrollment_id is None
            }
            candidates = []
            for duplicate in rows:
                if duplicate.status != EnrollmentStatus.WITHDRAWN.value:
                    continue
                if duplicate.reconciled_into_enrollment_id is not None:
                    continue
                if duplicate.reconciliation_reviewed_at is not None:
                    continue
                canonical = active_by_student.get(duplicate.student_id)
                if canonical is None or canonical.id == duplicate.id:
                    continue
                duplicate_range = EnrollmentService._effective_historical_range(
                    duplicate, sessions
                )
                canonical_range = self._canonical_range(canonical)
                if duplicate_range is None or canonical_range is None:
                    continue
                if not EnrollmentService._ranges_overlap(
                    canonical_range[0],
                    canonical_range[1],
                    duplicate_range[0],
                    duplicate_range[1],
                ):
                    continue
                if not self._canonical_covers(canonical, duplicate_range):
                    continue
                incomes = self._repository_provider.incomes(
                    session
                ).list_tuition_for_enrollment_including_history(int(duplicate.id))
                count, total = self._income_summary(incomes)
                student = getattr(duplicate, "student", None)
                candidates.append(
                    EnrollmentReconciliationCandidate(
                        student_id=int(duplicate.student_id),
                        student_name=getattr(student, "full_name", None)
                        or f"Student #{duplicate.student_id}",
                        class_id=int(duplicate.class_id),
                        class_name=duplicate.class_name or f"Class #{duplicate.class_id}",
                        canonical_enrollment_id=int(canonical.id),
                        duplicate_enrollment_id=int(duplicate.id),
                        canonical_range=canonical_range,
                        duplicate_effective_range=duplicate_range,
                        tuition_income_count=count,
                        tuition_income_total=total,
                        blockers=self._blockers(session, int(duplicate.id)),
                    )
                )
            return candidates

    def mark_legitimate(
        self,
        duplicate_enrollment_id: int,
        *,
        reason: str,
        actor=None,
    ) -> None:
        resolved_reason = self._require_reason(reason)
        resolved_actor = self._require_actor(actor)
        with self._session_factory() as session:
            repo = self._repository_provider.enrollments(session)
            enrollment = repo.get_by_id(duplicate_enrollment_id)
            if enrollment is None:
                raise EnrollmentReconciliationValidationError(
                    "Enrollment was not found."
                )
            if enrollment.reconciled_into_enrollment_id is not None:
                raise EnrollmentReconciliationValidationError(
                    "Enrollment has already been reconciled."
                )
            enrollment.reconciliation_reviewed_at = get_clock().now()
            enrollment.reconciliation_reviewed_by = getattr(
                resolved_actor, "username", None
            )
            enrollment.reconciliation_review_reason = resolved_reason
            self._audit_service.record_in_session(
                session,
                action="ENROLLMENT_RECONCILIATION_REVIEWED_LEGITIMATE",
                module="enrollment",
                target_type="enrollment",
                target_id=enrollment.id,
                target_name=enrollment.class_name,
                actor=resolved_actor,
                details={
                    "student_id": enrollment.student_id,
                    "class_id": enrollment.class_id,
                    "reason": resolved_reason,
                },
                summary=f"Enrollment#{enrollment.id} confirmed as legitimate history",
            )
            session.commit()

    def reconcile(
        self,
        duplicate_enrollment_id: int,
        canonical_enrollment_id: int,
        *,
        reason: str,
        actor=None,
    ) -> list[int]:
        """Reconcile one historical duplicate into an ACTIVE covering contract."""
        resolved_reason = self._require_reason(reason)
        resolved_actor = self._require_actor(actor)
        if duplicate_enrollment_id == canonical_enrollment_id:
            raise EnrollmentReconciliationValidationError(
                "Duplicate and canonical Enrollment must be different."
            )

        with self._session_factory() as session:
            repo = self._repository_provider.enrollments(session)
            duplicate = repo.get_by_id(duplicate_enrollment_id)
            canonical = repo.get_by_id(canonical_enrollment_id)
            if duplicate is None or canonical is None:
                raise EnrollmentReconciliationValidationError(
                    "Duplicate or canonical Enrollment was not found."
                )
            if duplicate.student_id != canonical.student_id or duplicate.class_id != canonical.class_id:
                raise EnrollmentReconciliationValidationError(
                    "Reconciliation requires the same Student and Class."
                )
            if duplicate.status != EnrollmentStatus.WITHDRAWN.value:
                raise EnrollmentReconciliationValidationError(
                    "Only a WITHDRAWN legacy Enrollment can be reconciled automatically."
                )
            if canonical.status != EnrollmentStatus.ACTIVE.value:
                raise EnrollmentReconciliationValidationError(
                    "Canonical Enrollment must be ACTIVE."
                )
            if duplicate.reconciled_into_enrollment_id is not None:
                raise EnrollmentReconciliationValidationError(
                    "Duplicate Enrollment has already been reconciled."
                )
            if canonical.reconciled_into_enrollment_id is not None:
                raise EnrollmentReconciliationValidationError(
                    "Canonical Enrollment cannot itself be reconciled."
                )

            blockers = self._blockers(session, int(duplicate.id))
            if blockers:
                raise EnrollmentReconciliationValidationError(
                    "Automatic reconciliation is blocked by immutable history: "
                    + ", ".join(blockers)
                )

            sessions = self._repository_provider.sessions(session).get_by_class(
                duplicate.class_id
            )
            duplicate_range = EnrollmentService._effective_historical_range(
                duplicate, sessions
            )
            if duplicate_range is None:
                raise EnrollmentReconciliationValidationError(
                    "Duplicate effective session range cannot be resolved safely."
                )
            if not self._canonical_covers(canonical, duplicate_range):
                raise EnrollmentReconciliationValidationError(
                    "Canonical Enrollment does not cover the duplicate's effective session range."
                )

            income_repo = self._repository_provider.incomes(session)
            moved_income_ids = income_repo.reattribute_tuition_enrollment(
                int(duplicate.id), int(canonical.id)
            )
            duplicate.reconciled_into_enrollment_id = int(canonical.id)
            duplicate.reconciled_at = get_clock().now()
            duplicate.reconciled_by = getattr(resolved_actor, "username", None)
            duplicate.reconcile_reason = resolved_reason
            duplicate.reconciliation_reviewed_at = None
            duplicate.reconciliation_reviewed_by = None
            duplicate.reconciliation_review_reason = None

            event_student_id = int(canonical.student_id)
            event_enrollment_id = int(canonical.id)
            event_class_id = int(canonical.class_id)
            event_status = canonical.status
            self._audit_service.record_in_session(
                session,
                action="ENROLLMENT_RECONCILED",
                module="enrollment",
                target_type="enrollment",
                target_id=duplicate.id,
                target_name=duplicate.class_name,
                actor=resolved_actor,
                details={
                    "student_id": duplicate.student_id,
                    "class_id": duplicate.class_id,
                    "duplicate_enrollment_id": duplicate.id,
                    "canonical_enrollment_id": canonical.id,
                    "duplicate_effective_range": list(duplicate_range),
                    "canonical_range": list(self._canonical_range(canonical) or ()),
                    "moved_tuition_income_ids": moved_income_ids,
                    "reason": resolved_reason,
                },
                summary=(
                    f"Reconciled Enrollment#{duplicate.id} into "
                    f"Enrollment#{canonical.id}"
                ),
            )
            session.commit()

        if self._event_bus is not None:
            self._event_bus.publish(
                FinanceDataChanged(
                    entity="enrollment_reconciliation",
                    action="RECONCILED",
                    entity_id=event_enrollment_id,
                )
            )
            self._event_bus.publish(
                StudentEnrollmentChanged(
                    student_id=event_student_id,
                    enrollment_id=event_enrollment_id,
                    class_id=event_class_id,
                    action="RECONCILED",
                    previous_status=event_status,
                    current_status=event_status,
                )
            )
        return moved_income_ids
