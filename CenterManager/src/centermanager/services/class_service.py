# -*- coding: utf-8 -*-
"""ClassService - business logic for Class entity."""
from datetime import date, datetime, timezone
from typing import Optional, List, Any

from sqlalchemy.orm import Session, sessionmaker

from centermanager.models.class_ import Class
from centermanager.models.student import Student          # <-- THÊM DÒNG NÀY
from centermanager.models.class_timeline_event import ClassTimelineEventType
from centermanager.models.enrollment import Enrollment
from centermanager.models.teacher import Teacher
from centermanager.models.teacher_assignment import TeacherAssignment
from centermanager.repositories.class_repository import ClassRepository
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.events.event_bus import EventBus
from centermanager.events.class_events import (
    ClassCreated, ClassUpdated, ClassArchived, ClassRestored,
)
from centermanager.services.exceptions import StudentServiceError, StudentValidationError

UNSET = object()


class ClassNotFoundError(StudentServiceError):
    pass


class ClassValidationError(StudentServiceError):
    pass


class ClassAlreadyDeletedError(StudentServiceError):
    pass


class ClassNotDeletedError(StudentServiceError):
    pass


class ClassFullError(StudentServiceError):
    pass


class ClassArchivedError(StudentServiceError):
    """Raised when a mutation targets an archived class."""
    pass


class StudentAlreadyEnrolledError(StudentServiceError):
    pass


class ClassService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: Optional[ClassTimelineService] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._event_bus = event_bus

    def _publish(self, event) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(event)

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_name(self, name: Optional[str]) -> str:
        normalized = self._normalize_text(name)
        if not normalized:
            raise ClassValidationError("Class name is required and cannot be blank.")
        return normalized

    def _generate_class_code(self, session: Session) -> str:
        repo = ClassRepository(session)
        highest = repo.get_highest_class_number()
        next_num = (highest or 0) + 1
        return f"CLS{next_num:03d}"

    def _require_active_class(self, class_obj: Optional[Class], class_id: int) -> Class:
        if class_obj is None:
            raise ClassNotFoundError(f"Class {class_id} not found.")
        if class_obj.deleted_at is not None:
            raise ClassArchivedError(
                f"Class {class_id} is archived and cannot be modified until restored."
            )
        return class_obj

    def _archive_snapshot(self, session: Session, class_id: int) -> dict:
        from centermanager.repositories.session_repository import SessionRepository
        from centermanager.repositories.teacher_assignment_repository import TeacherAssignmentRepository

        enrollment_repo = EnrollmentRepository(session)
        assignment_repo = TeacherAssignmentRepository(session)
        session_repo = SessionRepository(session)

        active_enrollments = len(enrollment_repo.get_active_by_class(class_id))
        teacher_assignments = len(assignment_repo.get_by_class(class_id))
        total_sessions = len(session_repo.get_by_class(class_id))
        return {
            "active_enrollments": active_enrollments,
            "teacher_assignments": teacher_assignments,
            "sessions": total_sessions,
        }

    # ===== CRUD =====

    def create_class(
        self,
        name: str,
        course: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        capacity: Optional[int] = None,
        status: str = "ACTIVE",
        fee: Optional[int] = None,
    ) -> Class:
        norm_name = self._validate_name(name)
        norm_course = self._normalize_text(course)

        with self._session_factory() as session:
            class_code = self._generate_class_code(session)
            class_obj = Class(
                name=norm_name,
                course=norm_course,
                start_date=start_date,
                end_date=end_date,
                capacity=capacity,
                status=status,
                fee=fee,
            )
            repo = ClassRepository(session)
            repo.add(class_obj)
            session.commit()
            session.refresh(class_obj)

            if self._timeline_service:
                self._timeline_service.log_event(
                    class_id=class_obj.id,
                    event_type=ClassTimelineEventType.CLASS_CREATED,
                    title="Class Created",
                    description=f"{class_obj.name} ({class_code}) was created.",
                    metadata={"class_code": class_code},
                )
            self._publish(ClassCreated(
                class_id=class_obj.id,
                class_name=class_obj.name,
            ))
            return class_obj

    def get_class(self, class_id: int) -> Class:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            class_obj = repo.get_by_id(class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise ClassNotFoundError(f"Class {class_id} not found or deleted.")
            return class_obj

    def get_class_with_details(self, class_id: int) -> Class:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            class_obj = repo.get_by_id_with_relations(class_id)
            if class_obj is None or class_obj.deleted_at is not None:
                raise ClassNotFoundError(f"Class {class_id} not found or deleted.")
            return class_obj

    def list_classes(self, include_archived: bool = False) -> List[Class]:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            if include_archived:
                return repo.list_all()
            return repo.list_active()

    def list_archived_classes(self) -> List[Class]:
        with self._session_factory() as session:
            return ClassRepository(session).list_archived()

    def search_classes(self, query: str) -> List[Class]:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            return repo.search_classes(query)

    def update_class(
        self,
        class_id: int,
        name: Any = UNSET,
        course: Any = UNSET,
        start_date: Any = UNSET,
        end_date: Any = UNSET,
        capacity: Any = UNSET,
        status: Any = UNSET,
        fee: Any = UNSET,
    ) -> Class:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            class_obj = repo.get_by_id(class_id)
            class_obj = self._require_active_class(class_obj, class_id)

            changes = []

            if name is not UNSET:
                new_val = self._validate_name(name)
                old_val = class_obj.name
                if old_val != new_val:
                    changes.append(f"name: '{old_val}' -> '{new_val}'")
                class_obj.name = new_val

            if course is not UNSET:
                new_val = self._normalize_text(course)
                old_val = class_obj.course or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"course: '{old_val}' -> '{new_val or '(none)'}'")
                class_obj.course = new_val

            if start_date is not UNSET:
                old = class_obj.start_date.strftime("%d/%m/%Y") if class_obj.start_date else "(none)"
                new = start_date.strftime("%d/%m/%Y") if start_date else "(none)"
                if old != new:
                    changes.append(f"start_date: '{old}' -> '{new}'")
                class_obj.start_date = start_date

            if end_date is not UNSET:
                old = class_obj.end_date.strftime("%d/%m/%Y") if class_obj.end_date else "(none)"
                new = end_date.strftime("%d/%m/%Y") if end_date else "(none)"
                if old != new:
                    changes.append(f"end_date: '{old}' -> '{new}'")
                class_obj.end_date = end_date

            if capacity is not UNSET:
                old = class_obj.capacity if class_obj.capacity is not None else "(none)"
                new = capacity if capacity is not None else "(none)"
                if str(old) != str(new):
                    changes.append(f"capacity: '{old}' -> '{new}'")
                class_obj.capacity = capacity

            if status is not UNSET:
                new_val = self._normalize_text(status) or "ACTIVE"
                old_val = class_obj.status
                if old_val != new_val:
                    changes.append(f"status: '{old_val}' -> '{new_val}'")
                class_obj.status = new_val
            if fee is not UNSET:
                new_val = fee
                old_val = class_obj.fee if class_obj.fee is not None else "(none)"
                if str(old_val) != str(new_val if new_val is not None else "(none)"):
                    changes.append(f"fee: '{old_val}' -> '{new_val if new_val is not None else '(none)'}'")
                class_obj.fee = new_val
            if not changes:
                return class_obj

            session.commit()
            session.refresh(class_obj)

            if self._timeline_service:
                self._timeline_service.log_event(
                    class_id=class_obj.id,
                    event_type=ClassTimelineEventType.CLASS_UPDATED,
                    title="Class Updated",
                    description="Updated: " + "; ".join(changes),
                    metadata={"changes": changes},
                )
            self._publish(ClassUpdated(
                class_id=class_obj.id,
                class_name=class_obj.name,
                changes=changes,
            ))
            return class_obj

    def archive_class(self, class_id: int) -> None:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            class_obj = repo.get_by_id(class_id)
            if class_obj is None:
                raise ClassNotFoundError(f"Class {class_id} not found.")
            if class_obj.deleted_at is not None:
                raise ClassAlreadyDeletedError(f"Class {class_id} already archived.")
            snapshot = self._archive_snapshot(session, class_id)
            class_obj.deleted_at = self._utc_now()
            session.commit()

            if self._timeline_service:
                self._timeline_service.log_event(
                    class_id=class_obj.id,
                    event_type=ClassTimelineEventType.CLASS_ARCHIVED,
                    title="Class Archived",
                    description=(
                        f"{class_obj.name} was archived. Historical teacher assignments, "
                        "enrollments, sessions, and attendance remain preserved and read-only "
                        "until the class is restored."
                    ),
                    metadata={"dependency_snapshot": snapshot},
                )

            self._publish(ClassArchived(
                class_id=class_obj.id,
                class_name=class_obj.name,
            ))

    def restore_class(self, class_id: int) -> None:
        with self._session_factory() as session:
            repo = ClassRepository(session)
            class_obj = repo.get_by_id(class_id)
            if class_obj is None:
                raise ClassNotFoundError(f"Class {class_id} not found.")
            if class_obj.deleted_at is None:
                raise ClassNotDeletedError(f"Class {class_id} is not archived.")
            class_obj.deleted_at = None
            session.commit()

            if self._timeline_service:
                self._timeline_service.log_event(
                    class_id=class_obj.id,
                    event_type=ClassTimelineEventType.CLASS_RESTORED,
                    title="Class Restored",
                    description=f"{class_obj.name} was restored.",
                )

            self._publish(ClassRestored(
                class_id=class_obj.id,
                class_name=class_obj.name,
            ))

    def list_active_teachers(self) -> List[Teacher]:
        """Return active teachers for class assignment UI."""
        with self._session_factory() as session:
            from centermanager.repositories.teacher_repository import TeacherRepository
            return TeacherRepository(session).list_active()

    def list_active_students(self) -> List[Student]:
        """Return active students for class enrollment UI."""
        with self._session_factory() as session:
            from centermanager.repositories.student_repository import StudentRepository
            return StudentRepository(session).list_active()

    # ===== Enrollment =====

    def enroll_student(self, class_id: int, student_id: int) -> Enrollment:
        """Compatibility facade. EnrollmentService owns the canonical lifecycle."""
        from centermanager.services.enrollment_service import (
            EnrollmentService, EnrollmentAlreadyActiveError, EnrollmentCapacityError
        )
        try:
            enrollment = EnrollmentService(self._session_factory, event_bus=self._event_bus).enroll(student_id, class_id)
        except EnrollmentAlreadyActiveError as exc:
            raise StudentAlreadyEnrolledError(str(exc)) from exc
        except EnrollmentCapacityError as exc:
            raise ClassFullError(str(exc)) from exc

        if self._timeline_service:
            with self._session_factory() as session:
                student = __import__(
                    "centermanager.repositories.student_repository",
                    fromlist=["StudentRepository"]
                ).StudentRepository(session).get_by_id(student_id)
            self._timeline_service.log_event(
                class_id=class_id,
                event_type=ClassTimelineEventType.STUDENT_ENROLLED,
                title="Student Enrolled",
                description=f"{student.full_name if student else 'Student'} enrolled in class.",
                metadata={"student_id": student_id},
            )
        return enrollment

    def remove_student(self, class_id: int, student_id: int) -> None:
        """Compatibility facade: remove now preserves history as WITHDRAWN."""
        from centermanager.services.enrollment_service import EnrollmentService, EnrollmentNotFoundError
        service = EnrollmentService(self._session_factory, event_bus=self._event_bus)
        with self._session_factory() as session:
            enrollment = EnrollmentRepository(session).get_active(student_id, class_id)
            if enrollment is None:
                raise ClassNotFoundError("Active enrollment not found.")
            enrollment_id = enrollment.id
        try:
            service.withdraw(enrollment_id)
        except EnrollmentNotFoundError as exc:
            raise ClassNotFoundError("Enrollment not found.") from exc

        if self._timeline_service:
            self._timeline_service.log_event(
                class_id=class_id,
                event_type=ClassTimelineEventType.STUDENT_REMOVED,
                title="Student Removed",
                description="Student withdrawn from class.",
                metadata={"student_id": student_id},
            )

    def get_enrolled_students(self, class_id: int) -> List[Student]:
        with self._session_factory() as session:
            enroll_repo = EnrollmentRepository(session)
            enrollments = enroll_repo.get_by_class_with_student(class_id)
            return [e.student for e in enrollments if e.student and e.status == "ACTIVE"]

    # ===== Teacher Assignment (using existing TeacherAssignmentService) =====

    def assign_teacher(self, class_id: int, teacher_id: int) -> TeacherAssignment:
        from centermanager.services.teacher_assignment_service import TeacherAssignmentService
        from centermanager.services.teacher_timeline_service import TeacherTimelineService

        timeline_service = TeacherTimelineService(self._session_factory)
        assignment_service = TeacherAssignmentService(
            self._session_factory, timeline_service, event_bus=self._event_bus
        )

        assignment = assignment_service.assign_teacher_to_class(teacher_id, class_id)

        if self._timeline_service:
            with self._session_factory() as session:
                from centermanager.repositories.teacher_repository import TeacherRepository
                teacher_repo = TeacherRepository(session)
                teacher = teacher_repo.get_by_id(teacher_id)
                teacher_name = teacher.full_name if teacher else f"Teacher #{teacher_id}"

            self._timeline_service.log_event(
                class_id=class_id,
                event_type=ClassTimelineEventType.TEACHER_ASSIGNED,
                title="Teacher Assigned",
                description=f"{teacher_name} assigned to class.",
                metadata={"teacher_id": teacher_id},
            )
        return assignment

    def remove_teacher(self, class_id: int, teacher_id: int) -> None:
        from centermanager.services.teacher_assignment_service import TeacherAssignmentService
        from centermanager.services.teacher_timeline_service import TeacherTimelineService

        timeline_service = TeacherTimelineService(self._session_factory)
        assignment_service = TeacherAssignmentService(
            self._session_factory, timeline_service, event_bus=self._event_bus
        )

        with self._session_factory() as session:
            from centermanager.repositories.teacher_repository import TeacherRepository
            teacher_repo = TeacherRepository(session)
            teacher = teacher_repo.get_by_id(teacher_id)
            teacher_name = teacher.full_name if teacher else f"Teacher #{teacher_id}"

        assignment_service.unassign_teacher_from_class(teacher_id, class_id)

        if self._timeline_service:
            self._timeline_service.log_event(
                class_id=class_id,
                event_type=ClassTimelineEventType.TEACHER_REMOVED,
                title="Teacher Removed",
                description=f"{teacher_name} removed from class.",
                metadata={"teacher_id": teacher_id},
            )

    def get_assigned_teachers(self, class_id: int) -> List[Teacher]:
        with self._session_factory() as session:
            class_obj = self.get_class_with_details(class_id)
            return class_obj.teachers