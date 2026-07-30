# -*- coding: utf-8 -*-
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from centermanager.models.student_highlight import StudentHighlight
from centermanager.repositories.base import BaseRepository


class StudentHighlightRepository(BaseRepository[StudentHighlight]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StudentHighlight)

    def find_by_session(self, session_id: int) -> List[StudentHighlight]:
        """Get all highlights for a session, with student loaded eagerly."""
        return (
            self._session.query(StudentHighlight)
            .options(joinedload(StudentHighlight.student))
            .filter(StudentHighlight.session_id == session_id)
            .order_by(desc(StudentHighlight.created_at))
            .all()
        )

    def find_by_student(self, student_id: int) -> List[StudentHighlight]:
        return (
            self._session.query(StudentHighlight)
            .options(joinedload(StudentHighlight.student))
            .filter(StudentHighlight.student_id == student_id)
            .order_by(desc(StudentHighlight.created_at))
            .all()
        )

    def find_by_session_and_student(
        self, session_id: int, student_id: int
    ) -> List[StudentHighlight]:
        return (
            self._session.query(StudentHighlight)
            .options(joinedload(StudentHighlight.student))
            .filter(
                StudentHighlight.session_id == session_id,
                StudentHighlight.student_id == student_id,
            )
            .order_by(desc(StudentHighlight.created_at))
            .all()
        )

    def add(self, highlight: StudentHighlight) -> StudentHighlight:
        self._session.add(highlight)
        return highlight

    def delete(self, highlight: StudentHighlight) -> None:
        self._session.delete(highlight)