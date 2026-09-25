# -*- coding: utf-8 -*-
"""Canonical Enrollment lifecycle service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Callable, List, Optional

from centermanager.core.capabilities import Capability
from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.models.enrollment import Enrollment
from centermanager.models.enrollment_freeze import EnrollmentFreeze
from centermanager.models.session import SessionStatus
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentEnrollmentChanged
from centermanager.services.audit_service import AuditService
from centermanager.services.authorization_service import AuthorizationService


class EnrollmentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"


class EnrollmentError(Exception): pass
class EnrollmentNotFoundError(EnrollmentError): pass
class EnrollmentAlreadyActiveError(EnrollmentError): pass
class InvalidEnrollmentTransitionError(EnrollmentError): pass
class EnrollmentCapacityError(EnrollmentError): pass
class EnrollmentValidationError(EnrollmentError): pass


_MONEY_QUANTUM = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class EnrollmentService:
    """Owns Enrollment lifecycle while preserving historical rows.

    Tuition terms are snapshotted when a new enrollment is created. Historical
    rows created before the tuition-contract migration deliberately remain
    unresolved rather than inheriting today's Class contract retroactively.
    """

    def __init__(
        self,
        session_factory: Callable,
        event_bus: Optional[EventBus] = None,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()
        self._audit_service = audit_service or AuditService(
            session_factory,
            repository_provider=self._repository_provider,
        )

    def _publish_change(
        self, enrollment: Enrollment, action: str, previous_status: Optional[str]
    ) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(StudentEnrollmentChanged(
            student_id=enrollment.student_id,
            enrollment_id=enrollment.id,
            class_id=enrollment.class_id,
            action=action,
            previous_status=previous_status,
            current_status=enrollment.status,
        ))

    @staticmethod
    def _snapshot_tuition_contract(
        class_obj,
        *,
        enrolled_from_session: int,
        enrolled_until_session: Optional[int],
        discount_amount: Decimal | int,
    ) -> dict:
        if not class_obj.has_course_contract:
            raise EnrollmentValidationError(
                "Class course contract is incomplete; complete tuition terms before enrolling students."
            )
        class_planned_sessions = int(class_obj.planned_sessions)
        effective_until = class_planned_sessions if enrolled_until_session is None else enrolled_until_session
        if enrolled_from_session < 1 or enrolled_from_session > class_planned_sessions:
            raise EnrollmentValidationError(
                f"Enrollment start session must be between 1 and {class_planned_sessions}."
            )
        if effective_until < enrolled_from_session or effective_until > class_planned_sessions:
            raise EnrollmentValidationError(
                f"Enrollment end session must be between {enrolled_from_session} and {class_planned_sessions}."
            )
        try:
            discount = _money(Decimal(str(discount_amount)))
        except Exception as exc:
            raise EnrollmentValidationError("Discount amount must be a valid number.") from exc
        if discount < 0:
            raise EnrollmentValidationError("Discount amount cannot be negative.")
        contracted_sessions = effective_until - enrolled_from_session + 1
        class_fee = Decimal(class_obj.course_fee)
        agreed_course_fee = _money(class_fee * Decimal(contracted_sessions) / Decimal(class_planned_sessions))
        unit_fee = _money(agreed_course_fee / Decimal(contracted_sessions))
        if discount > agreed_course_fee:
            raise EnrollmentValidationError("Discount amount cannot exceed the agreed course fee.")
        return {
            "agreed_course_fee": agreed_course_fee,
            "planned_sessions": contracted_sessions,
            "unit_fee": unit_fee,
            "enrolled_from_session": enrolled_from_session,
            "enrolled_until_session": effective_until,
            "discount_amount": discount,
        }

    @staticmethod
    def _resolved_start_session(class_obj, sessions) -> tuple[int, str]:
        if not class_obj.has_course_contract:
            raise EnrollmentValidationError(
                "Class course contract is incomplete; complete tuition terms before enrolling students."
            )
        completed_numbers = [int(item.session_number) for item in sessions if item.status == SessionStatus.COMPLETED.value]
        if not completed_numbers:
            return 1, "NO_COMPLETED_SESSIONS"
        next_session = max(completed_numbers) + 1
        if next_session > int(class_obj.planned_sessions):
            raise EnrollmentValidationError(
                "The class has already completed all planned sessions; a new enrollment cannot be created."
            )
        return next_session, "AFTER_LAST_COMPLETED_SESSION"

    def preview_enrollment_pricing(
        self,
        class_id: int,
        *,
        enrolled_from_session: Optional[int] = None,
        enrolled_until_session: Optional[int] = None,
        discount_amount: Decimal | int = 0,
    ) -> dict:
        with self._session_factory() as session:
            class_obj = self._repository_provider.classes(session).get_by_id(class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise EnrollmentError("Class not found or archived.")
            resolution = "EXPLICIT"
            effective_from = enrolled_from_session
            if effective_from is None:
                sessions = self._repository_provider.sessions(session).get_by_class(class_id)
                effective_from, resolution = self._resolved_start_session(class_obj, sessions)
            snapshot = self._snapshot_tuition_contract(
                class_obj,
                enrolled_from_session=int(effective_from),
                enrolled_until_session=enrolled_until_session,
                discount_amount=discount_amount,
            )
            return {
                **snapshot,
                "suggested_agreed_course_fee": snapshot["agreed_course_fee"],
                "class_planned_sessions": int(class_obj.planned_sessions),
                "class_course_fee": _money(Decimal(class_obj.course_fee)),
                "resolution": resolution,
            }

    @staticmethod
    def _apply_agreed_fee_override(snapshot: dict, override_value: Decimal | int) -> dict:
        try:
            override_fee = _money(Decimal(str(override_value)))
        except Exception as exc:
            raise EnrollmentValidationError("Agreed fee override must be a valid number.") from exc
        if override_fee < 0:
            raise EnrollmentValidationError("Agreed fee override cannot be negative.")
        if snapshot["discount_amount"] > override_fee:
            raise EnrollmentValidationError("Discount amount cannot exceed the overridden agreed course fee.")
        result = dict(snapshot)
        result["agreed_course_fee"] = override_fee
        result["unit_fee"] = _money(override_fee / Decimal(result["planned_sessions"]))
        return result

    def enroll(
        self,
        student_id: int,
        class_id: int,
        start_date: Optional[date] = None,
        *,
        enrolled_from_session: Optional[int] = None,
        enrolled_until_session: Optional[int] = None,
        discount_amount: Decimal | int = 0,
        agreed_course_fee_override: Optional[Decimal | int] = None,
        override_reason: Optional[str] = None,
        actor=None,
    ) -> Enrollment:
        with self._session_factory() as session:
            class_obj = self._repository_provider.classes(session).get_by_id(class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise EnrollmentError("Class not found or archived.")
            student = self._repository_provider.students(session).get_by_id(student_id)
            if student is None or student.deleted_at is not None:
                raise EnrollmentError("Student not found or inactive.")
            repo = self._repository_provider.enrollments(session)
            if repo.exists(student_id, class_id, active_only=True):
                raise EnrollmentAlreadyActiveError("Student already has an active enrollment in this class.")
            if class_obj.capacity is not None and len(repo.get_active_by_class(class_id)) >= class_obj.capacity:
                raise EnrollmentCapacityError(f"Class capacity ({class_obj.capacity}) reached.")
            effective_from = enrolled_from_session
            if effective_from is None:
                session_factory = getattr(self._repository_provider, "sessions", None)
                if callable(session_factory):
                    sessions = session_factory(session).get_by_class(class_id)
                    effective_from, _ = self._resolved_start_session(class_obj, sessions)
                else:
                    effective_from = 1
            tuition_snapshot = self._snapshot_tuition_contract(
                class_obj,
                enrolled_from_session=int(effective_from),
                enrolled_until_session=enrolled_until_session,
                discount_amount=discount_amount,
            )
            suggested_fee = tuition_snapshot["agreed_course_fee"]
            resolved_actor = actor if actor is not None else get_current_user()
            reason = (override_reason or "").strip()
            if agreed_course_fee_override is not None:
                AuthorizationService.require(resolved_actor, Capability.TUITION_ENROLLMENT_OVERRIDE)
                if not reason:
                    raise EnrollmentValidationError(
                        "A reason is required when overriding the suggested agreed course fee."
                    )
                tuition_snapshot = self._apply_agreed_fee_override(tuition_snapshot, agreed_course_fee_override)
            enrollment = Enrollment(
                student_id=student_id,
                class_id=class_id,
                class_name=class_obj.name,
                course_name=class_obj.course,
                start_date=start_date or class_obj.start_date or get_clock().today(),
                status=EnrollmentStatus.ACTIVE.value,
                **tuition_snapshot,
            )
            repo.add(enrollment)
            if agreed_course_fee_override is not None:
                flush = getattr(repo, "flush", None)
                if callable(flush):
                    flush()
                self._audit_service.record_in_session(
                    session,
                    action="TUITION_ENROLLMENT_FEE_OVERRIDE",
                    module="tuition",
                    target_type="enrollment",
                    target_id=enrollment.id,
                    target_name=class_obj.name,
                    actor=resolved_actor,
                    details={
                        "student_id": student_id,
                        "class_id": class_id,
                        "enrolled_from_session": tuition_snapshot["enrolled_from_session"],
                        "enrolled_until_session": tuition_snapshot["enrolled_until_session"],
                        "planned_sessions": tuition_snapshot["planned_sessions"],
                        "suggested_agreed_course_fee": str(suggested_fee),
                        "overridden_agreed_course_fee": str(tuition_snapshot["agreed_course_fee"]),
                        "reason": reason,
                    },
                    summary=f"Tuition fee override for enrollment in {class_obj.name}",
                )
            session.commit()
            repo.refresh(enrollment)
            self._publish_change(enrollment, "ENROLLED", None)
            return enrollment

    @staticmethod
    def _ranges_overlap(start_a: int, end_a: Optional[int], start_b: int, end_b: Optional[int]) -> bool:
        infinity = 2**31 - 1
        return int(start_a) <= int(end_b if end_b is not None else infinity) and int(start_b) <= int(end_a if end_a is not None else infinity)

    @staticmethod
    def _require_reason(reason: Optional[str], label: str) -> str:
        resolved = (reason or "").strip()
        if not resolved:
            raise EnrollmentValidationError(f"{label} reason is required.")
        return resolved

    @staticmethod
    def _require_active_tuition_range(enrollment: Enrollment) -> tuple[int, int]:
        if enrollment.status != EnrollmentStatus.ACTIVE.value:
            raise EnrollmentValidationError("Only an ACTIVE enrollment can be frozen or resumed.")
        start = enrollment.enrolled_from_session
        end = enrollment.enrolled_until_session
        if start is None or end is None:
            raise EnrollmentValidationError("Enrollment tuition session range is unresolved.")
        return int(start), int(end)

    @staticmethod
    def _require_freeze_capability(actor) -> None:
        if actor is not None:
            AuthorizationService.require(actor, Capability.STUDENT_UPDATE)

    def list_freezes(self, enrollment_id: int) -> List[EnrollmentFreeze]:
        with self._session_factory() as session:
            if self._repository_provider.enrollments(session).get_by_id(enrollment_id) is None:
                raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found.")
            return self._repository_provider.enrollment_freezes(session).list_for_enrollment(enrollment_id)

    def freeze(
        self,
        enrollment_id: int,
        start_session: int,
        reason: str,
        *,
        end_session: Optional[int] = None,
        actor=None,
    ) -> EnrollmentFreeze:
        """Pause tuition for an explicit session range without changing Sessions."""
        freeze_reason = self._require_reason(reason, "Freeze")
        resolved_actor = actor if actor is not None else get_current_user()
        self._require_freeze_capability(resolved_actor)
        with self._session_factory() as session:
            enrollment_repo = self._repository_provider.enrollments(session)
            enrollment = enrollment_repo.get_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found.")
            range_start, range_end = self._require_active_tuition_range(enrollment)
            start_session = int(start_session)
            end_session = int(end_session) if end_session is not None else None
            if start_session < range_start or start_session > range_end:
                raise EnrollmentValidationError(
                    f"Freeze start session must be between {range_start} and {range_end}."
                )
            if end_session is not None and (end_session < start_session or end_session > range_end):
                raise EnrollmentValidationError(
                    f"Freeze end session must be between {start_session} and {range_end}."
                )
            sessions = self._repository_provider.sessions(session).get_by_class(enrollment.class_id)
            completed_numbers = [
                int(item.session_number)
                for item in sessions
                if item.status == SessionStatus.COMPLETED.value
            ]
            if completed_numbers and start_session <= max(completed_numbers):
                raise EnrollmentValidationError(
                    "Freeze cannot start on or before an already completed session; historical tuition cannot be reinterpreted."
                )
            freeze_repo = self._repository_provider.enrollment_freezes(session)
            existing = freeze_repo.list_for_enrollment(enrollment_id)
            if any(self._ranges_overlap(start_session, end_session, item.start_session, item.end_session) for item in existing):
                raise EnrollmentValidationError("Freeze range overlaps existing Enrollment freeze history.")
            freeze = EnrollmentFreeze(
                enrollment_id=enrollment_id,
                start_session=start_session,
                end_session=end_session,
                reason=freeze_reason,
                created_by=getattr(resolved_actor, "username", None),
            )
            freeze_repo.add(freeze)
            freeze_repo.flush()
            self._audit_service.record_in_session(
                session,
                action="TUITION_ENROLLMENT_FREEZE",
                module="tuition",
                target_type="enrollment",
                target_id=enrollment_id,
                target_name=enrollment.class_name,
                actor=resolved_actor,
                details={
                    "freeze_id": freeze.id,
                    "start_session": start_session,
                    "end_session": end_session,
                    "reason": freeze_reason,
                },
                summary=f"Tuition freeze for enrollment #{enrollment_id}",
            )
            session.commit()
            freeze_repo.refresh(freeze)
            self._publish_change(enrollment, "TUITION_FROZEN", enrollment.status)
            return freeze

    def resume(
        self,
        enrollment_id: int,
        end_session: int,
        reason: str,
        *,
        actor=None,
    ) -> EnrollmentFreeze:
        """Close the currently open freeze; tuition resumes after end_session."""
        resume_reason = self._require_reason(reason, "Resume")
        resolved_actor = actor if actor is not None else get_current_user()
        self._require_freeze_capability(resolved_actor)
        with self._session_factory() as session:
            enrollment_repo = self._repository_provider.enrollments(session)
            enrollment = enrollment_repo.get_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found.")
            _, range_end = self._require_active_tuition_range(enrollment)
            freeze_repo = self._repository_provider.enrollment_freezes(session)
            freeze = freeze_repo.get_open(enrollment_id)
            if freeze is None:
                raise EnrollmentValidationError("Enrollment has no open tuition freeze to resume.")
            end_session = int(end_session)
            if end_session < int(freeze.start_session) or end_session > range_end:
                raise EnrollmentValidationError(
                    f"Last frozen session must be between {freeze.start_session} and {range_end}."
                )
            freeze.end_session = end_session
            freeze.resumed_at = get_clock().now()
            freeze.resume_reason = resume_reason
            freeze.resumed_by = getattr(resolved_actor, "username", None)
            self._audit_service.record_in_session(
                session,
                action="TUITION_ENROLLMENT_RESUME",
                module="tuition",
                target_type="enrollment",
                target_id=enrollment_id,
                target_name=enrollment.class_name,
                actor=resolved_actor,
                details={
                    "freeze_id": freeze.id,
                    "start_session": freeze.start_session,
                    "end_session": end_session,
                    "reason": resume_reason,
                },
                summary=f"Tuition resume for enrollment #{enrollment_id}",
            )
            session.commit()
            freeze_repo.refresh(freeze)
            self._publish_change(enrollment, "TUITION_RESUMED", enrollment.status)
            return freeze

    def withdraw(self, enrollment_id: int, end_date: Optional[date] = None) -> Enrollment:
        return self._transition(enrollment_id, EnrollmentStatus.WITHDRAWN, end_date)

    def complete(self, enrollment_id: int, end_date: Optional[date] = None) -> Enrollment:
        return self._transition(enrollment_id, EnrollmentStatus.COMPLETED, end_date)

    def _transition(self, enrollment_id: int, target: EnrollmentStatus, end_date: Optional[date]) -> Enrollment:
        with self._session_factory() as session:
            repo = self._repository_provider.enrollments(session)
            enrollment = repo.get_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found.")
            class_obj = self._repository_provider.classes(session).get_by_id(enrollment.class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise EnrollmentValidationError(
                    f"Archived class {enrollment.class_id} cannot change enrollments until restored."
                )
            if enrollment.status != EnrollmentStatus.ACTIVE.value:
                raise InvalidEnrollmentTransitionError(
                    f"Cannot transition {enrollment.status!r} enrollment to {target.value}."
                )
            freeze_factory = getattr(self._repository_provider, "enrollment_freezes", None)
            if callable(freeze_factory) and freeze_factory(session).get_open(enrollment_id) is not None:
                raise InvalidEnrollmentTransitionError(
                    "Resume the open tuition freeze before completing or withdrawing this enrollment."
                )
            previous_status = enrollment.status
            enrollment.status = target.value
            enrollment.end_date = end_date or get_clock().today()
            session.commit()
            repo.refresh(enrollment)
            self._publish_change(
                enrollment,
                "COMPLETED" if target == EnrollmentStatus.COMPLETED else "WITHDRAWN",
                previous_status,
            )
            return enrollment

    def get_student_history(self, student_id: int) -> List[Enrollment]:
        with self._session_factory() as session:
            return self._repository_provider.enrollments(session).get_by_student(student_id)

    def get_active_students(self, class_id: int):
        with self._session_factory() as session:
            return [
                e.student
                for e in self._repository_provider.enrollments(session).get_by_class_with_student(class_id)
                if e.status == EnrollmentStatus.ACTIVE.value and e.student
            ]
