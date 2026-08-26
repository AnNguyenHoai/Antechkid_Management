# -*- coding: utf-8 -*-
"""Canonical Enrollment lifecycle service."""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Callable, List, Optional

from centermanager.models.enrollment import Enrollment
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.repositories.student_repository import StudentRepository
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import StudentEnrollmentChanged


class EnrollmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"


class EnrollmentError(Exception): pass
class EnrollmentNotFoundError(EnrollmentError): pass
class EnrollmentAlreadyActiveError(EnrollmentError): pass
class InvalidEnrollmentTransitionError(EnrollmentError): pass
class EnrollmentCapacityError(EnrollmentError): pass


class EnrollmentService:
    """Owns Enrollment lifecycle while preserving historical rows."""

    def __init__(self, session_factory: Callable, event_bus: Optional[EventBus] = None):
        self._session_factory = session_factory
        self._event_bus = event_bus

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

    def enroll(self, student_id: int, class_id: int, start_date: Optional[date] = None) -> Enrollment:
        with self._session_factory() as session:
            class_obj = ClassRepository(session).get_by_id(class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise EnrollmentError("Class not found or archived.")
            student = StudentRepository(session).get_by_id(student_id)
            if student is None or student.deleted_at is not None:
                raise EnrollmentError("Student not found or inactive.")

            repo = EnrollmentRepository(session)
            if repo.exists(student_id, class_id, active_only=True):
                raise EnrollmentAlreadyActiveError("Student already has an active enrollment in this class.")
            if class_obj.capacity is not None and len(repo.get_active_by_class(class_id)) >= class_obj.capacity:
                raise EnrollmentCapacityError(f"Class capacity ({class_obj.capacity}) reached.")

            enrollment = Enrollment(
                student_id=student_id, class_id=class_id,
                class_name=class_obj.name, course_name=class_obj.course,
                start_date=start_date or class_obj.start_date or date.today(),
                status=EnrollmentStatus.ACTIVE.value,
            )
            repo.add(enrollment)
            session.commit(); session.refresh(enrollment)
            self._publish_change(enrollment, "ENROLLED", None)
            return enrollment

    def withdraw(self, enrollment_id: int, end_date: Optional[date] = None) -> Enrollment:
        return self._transition(enrollment_id, EnrollmentStatus.WITHDRAWN, end_date)

    def complete(self, enrollment_id: int, end_date: Optional[date] = None) -> Enrollment:
        return self._transition(enrollment_id, EnrollmentStatus.COMPLETED, end_date)

    def _transition(self, enrollment_id: int, target: EnrollmentStatus, end_date: Optional[date]) -> Enrollment:
        with self._session_factory() as session:
            enrollment = EnrollmentRepository(session).get_by_id(enrollment_id)
            if enrollment is None:
                raise EnrollmentNotFoundError(f"Enrollment {enrollment_id} not found.")
            if enrollment.status != EnrollmentStatus.ACTIVE.value:
                raise InvalidEnrollmentTransitionError(
                    f"Cannot transition {enrollment.status!r} enrollment to {target.value}."
                )
            previous_status = enrollment.status
            enrollment.status = target.value
            enrollment.end_date = end_date or date.today()
            session.commit(); session.refresh(enrollment)
            self._publish_change(
                enrollment,
                "COMPLETED" if target == EnrollmentStatus.COMPLETED else "WITHDRAWN",
                previous_status,
            )
            return enrollment

    def get_student_history(self, student_id: int) -> List[Enrollment]:
        with self._session_factory() as session:
            return EnrollmentRepository(session).get_by_student(student_id)

    def get_active_students(self, class_id: int):
        with self._session_factory() as session:
            return [e.student for e in EnrollmentRepository(session).get_by_class_with_student(class_id)
                    if e.status == EnrollmentStatus.ACTIVE.value and e.student]
