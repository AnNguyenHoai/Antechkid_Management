# -*- coding: utf-8 -*-
"""
TeacherAssignmentService - manage teacher-class assignments.
"""
from typing import List

from sqlalchemy.orm import sessionmaker

from centermanager.models.teacher_assignment import TeacherAssignment
from centermanager.models.teacher import Teacher
from centermanager.repositories.teacher_repository import TeacherRepository
from centermanager.models.teacher_timeline_event import TeacherTimelineEventType
from centermanager.repositories.teacher_assignment_repository import TeacherAssignmentRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.events.event_bus import EventBus
from centermanager.events.teacher_events import TeacherAssignmentChanged


class TeacherAssignmentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TeacherTimelineService,
        event_bus: EventBus | None = None
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._event_bus = event_bus

    def assign_teacher_to_class(self, teacher_id: int, class_id: int) -> TeacherAssignment:
        with self._session_factory() as session:
            teacher = TeacherRepository(session).get_by_id(teacher_id)
            if teacher is None:
                raise ValueError(f"Teacher {teacher_id} not found.")
            if teacher.deleted_at is not None:
                raise ValueError(f"Archived teacher {teacher_id} cannot be assigned to a class.")
            if teacher.status != Teacher.STATUS_ACTIVE:
                raise ValueError(f"Inactive teacher {teacher_id} cannot accept new class assignments.")

            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is None:
                raise ValueError(f"Class {class_id} not found.")
            if class_obj.deleted_at is not None:
                raise ValueError(f"Archived class {class_id} cannot receive teacher assignments.")
            if class_obj.status != "ACTIVE":
                raise ValueError(f"Inactive class {class_id} cannot receive teacher assignments.")

            # Check if already assigned
            repo = TeacherAssignmentRepository(session)
            if repo.exists(teacher_id, class_id):
                raise ValueError(f"Teacher {teacher_id} is already assigned to class {class_id}.")

            # Class was validated above.
            class_name = class_obj.name

            assignment = TeacherAssignment(teacher_id=teacher_id, class_id=class_id)
            repo.add(assignment)
            session.commit()
            session.refresh(assignment)

            self._timeline_service.log_event(
                teacher_id=teacher_id,
                event_type=TeacherTimelineEventType.TEACHER_ASSIGNED,
                title="Teacher Assigned to Class",
                description=f"Assigned to {class_name}",
                metadata={"class_id": class_id, "class_name": class_name}
            )
            if self._event_bus:
                self._event_bus.publish(TeacherAssignmentChanged(
                    teacher_id=teacher_id,
                    assignment_id=assignment.id,
                    class_id=class_id,
                    action="assigned",
                ))
            return assignment

    def unassign_teacher_from_class(self, teacher_id: int, class_id: int) -> None:
        with self._session_factory() as session:
            repo = TeacherAssignmentRepository(session)
            assignment = repo.get_assignment(teacher_id, class_id)
            if assignment is None:
                raise ValueError(f"Teacher {teacher_id} is not assigned to class {class_id}.")

            # Get class name for timeline
            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is not None and class_obj.deleted_at is not None:
                raise ValueError(
                    f"Archived class {class_id} cannot change teacher assignments until restored."
                )
            class_name = class_obj.name if class_obj else f"Class #{class_id}"

            assignment_id = assignment.id
            repo.delete(assignment)
            session.commit()

            self._timeline_service.log_event(
                teacher_id=teacher_id,
                event_type=TeacherTimelineEventType.TEACHER_UNASSIGNED,
                title="Teacher Unassigned from Class",
                description=f"Unassigned from {class_name}",
                metadata={"class_id": class_id, "class_name": class_name}
            )
            if self._event_bus:
                self._event_bus.publish(TeacherAssignmentChanged(
                    teacher_id=teacher_id,
                    assignment_id=assignment_id,
                    class_id=class_id,
                    action="unassigned",
                ))


    def list_available_classes(self):
        with self._session_factory() as session:
            return ClassRepository(session).list_active()

    def get_assigned_classes(self, teacher_id: int) -> List[int]:
        with self._session_factory() as session:
            repo = TeacherAssignmentRepository(session)
            assignments = repo.get_by_teacher(teacher_id)
            return [a.class_id for a in assignments]

    def get_teachers_for_class(self, class_id: int) -> List[int]:
        with self._session_factory() as session:
            repo = TeacherAssignmentRepository(session)
            assignments = repo.get_by_class(class_id)
            return [a.teacher_id for a in assignments]