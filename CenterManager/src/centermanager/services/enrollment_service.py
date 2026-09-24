# -*- coding: utf-8 -*-
"""Canonical Enrollment lifecycle service."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Callable, List, Optional

from centermanager.core.clock import get_clock
from centermanager.models.enrollment import Enrollment
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentEnrollmentChanged


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
    ):
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

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
        """Build an immutable tuition snapshot from the current Class contract.

        Mid-course enrollment is explicit: callers provide the first effective
        class-session ordinal instead of inferring it from dates. Enrollment
        ``planned_sessions`` is the number of sessions in that student's
        effective contract, while ``enrolled_from_session``/``until`` retain the
        corresponding Class session range. This preserves the invariant
        ``unit_fee = agreed_course_fee / planned_sessions``.
        """
        if not class_obj.has_course_contract:
            raise EnrollmentValidationError(
                "Class course contract is incomplete; complete tuition terms before enrolling students."
            )

        class_planned_sessions = int(class_obj.planned_sessions)
        effective_until = (
            class_planned_sessions if enrolled_until_session is None else enrolled_until_session
        )
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
        agreed_course_fee = _money(
            class_fee * Decimal(contracted_sessions) / Decimal(class_planned_sessions)
        )
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

    def enroll(
        self,
        student_id: int,
        class_id: int,
        start_date: Optional[date] = None,
        *,
        enrolled_from_session: int = 1,
        enrolled_until_session: Optional[int] = None,
        discount_amount: Decimal | int = 0,
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

            tuition_snapshot = self._snapshot_tuition_contract(
                class_obj,
                enrolled_from_session=enrolled_from_session,
                enrolled_until_session=enrolled_until_session,
                discount_amount=discount_amount,
            )
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
            session.commit()
            repo.refresh(enrollment)
            self._publish_change(enrollment, "ENROLLED", None)
            return enrollment

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
            return [e.student for e in self._repository_provider.enrollments(session).get_by_class_with_student(class_id)
                    if e.status == EnrollmentStatus.ACTIVE.value and e.student]
