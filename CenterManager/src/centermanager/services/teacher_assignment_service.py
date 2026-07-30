# -*- coding: utf-8 -*-
"""
TeacherAssignmentService - manage teacher-class assignments.
"""
from typing import List

from sqlalchemy.orm import sessionmaker

from centermanager.models.teacher_assignment import TeacherAssignment
from centermanager.models.teacher_timeline_event import TeacherTimelineEventType
from centermanager.repositories.teacher_assignment_repository import TeacherAssignmentRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.services.teacher_timeline_service import TeacherTimelineService


class TeacherAssignmentService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: TeacherTimelineService
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service

    def assign_teacher_to_class(self, teacher_id: int, class_id: int) -> TeacherAssignment:
        with self._session_factory() as session:
            # Check if already assigned
            repo = TeacherAssignmentRepository(session)
            if repo.exists(teacher_id, class_id):
                raise ValueError(f"Teacher {teacher_id} is already assigned to class {class_id}.")

            # Get class name for timeline
            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            class_name = class_obj.name if class_obj else f"Class #{class_id}"

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
            return assignment

    def unassign_teacher_from_class(self, teacher_id: int, class_id: int) -> None:
        with self._session_factory() as session:
            repo = TeacherAssignmentRepository(session)
            assignment = repo._session.query(TeacherAssignment).filter(
                TeacherAssignment.teacher_id == teacher_id,
                TeacherAssignment.class_id == class_id
            ).first()
            if assignment is None:
                raise ValueError(f"Teacher {teacher_id} is not assigned to class {class_id}.")

            # Get class name for timeline
            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            class_name = class_obj.name if class_obj else f"Class #{class_id}"

            repo.delete(assignment)
            session.commit()

            self._timeline_service.log_event(
                teacher_id=teacher_id,
                event_type=TeacherTimelineEventType.TEACHER_UNASSIGNED,
                title="Teacher Unassigned from Class",
                description=f"Unassigned from {class_name}",
                metadata={"class_id": class_id, "class_name": class_name}
            )

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