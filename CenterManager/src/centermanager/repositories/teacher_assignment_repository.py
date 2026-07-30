# -*- coding: utf-8 -*-
"""
TeacherAssignment repository - data access for teacher-class assignments.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.teacher_assignment import TeacherAssignment
from centermanager.repositories.base import BaseRepository


class TeacherAssignmentRepository(BaseRepository[TeacherAssignment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TeacherAssignment)

    def get_by_teacher(self, teacher_id: int) -> List[TeacherAssignment]:
        return self._session.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == teacher_id
        ).all()

    def get_by_class(self, class_id: int) -> List[TeacherAssignment]:
        return self._session.query(TeacherAssignment).filter(
            TeacherAssignment.class_id == class_id
        ).all()

    def exists(self, teacher_id: int, class_id: int) -> bool:
        return self._session.query(TeacherAssignment).filter(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == class_id
        ).first() is not None

    def add(self, assignment: TeacherAssignment) -> TeacherAssignment:
        self._session.add(assignment)
        return assignment

    def delete(self, assignment: TeacherAssignment) -> None:
        self._session.delete(assignment)