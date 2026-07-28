# -*- coding: utf-8 -*-
"""
StudentHighlight repository - data access for StudentHighlight entity.
"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.student_highlight import StudentHighlight
from centermanager.repositories.base import BaseRepository


class StudentHighlightRepository(BaseRepository[StudentHighlight]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, StudentHighlight)

    def find_by_session(self, session_id: int) -> List[StudentHighlight]:
        """Get all highlights for a session."""
        return self._session.query(StudentHighlight).filter(
            StudentHighlight.session_id == session_id
        ).order_by(desc(StudentHighlight.created_at)).all()

    def find_by_student(self, student_id: int) -> List[StudentHighlight]:
        """Get all highlights for a student."""
        return self._session.query(StudentHighlight).filter(
            StudentHighlight.student_id == student_id
        ).order_by(desc(StudentHighlight.created_at)).all()

    def find_by_session_and_student(self, session_id: int, student_id: int) -> List[StudentHighlight]:
        """Get highlights for a specific student in a session."""
        return self._session.query(StudentHighlight).filter(
            StudentHighlight.session_id == session_id,
            StudentHighlight.student_id == student_id
        ).order_by(desc(StudentHighlight.created_at)).all()

    def add(self, highlight: StudentHighlight) -> StudentHighlight:
        self._session.add(highlight)
        return highlight

    def delete(self, highlight: StudentHighlight) -> None:
        self._session.delete(highlight)