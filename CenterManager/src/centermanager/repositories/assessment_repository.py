# -*- coding: utf-8 -*-
"""
Assessment repository - data access for Assessment entity.
"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.assessment import Assessment
from centermanager.repositories.base import BaseRepository


class AssessmentRepository(BaseRepository[Assessment]):
    """Repository for Assessment entity."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Assessment)

    def get_by_student(self, student_id: int) -> List[Assessment]:
        """Get all assessments for a student, ordered by date desc."""
        return self._session.query(Assessment).filter(
            Assessment.student_id == student_id
        ).order_by(desc(Assessment.assessment_date), desc(Assessment.created_at)).all()

    def get_latest(self, student_id: int) -> Optional[Assessment]:
        """Get the most recent assessment for a student."""
        return self._session.query(Assessment).filter(
            Assessment.student_id == student_id
        ).order_by(desc(Assessment.assessment_date), desc(Assessment.created_at)).first()

    def add(self, assessment: Assessment) -> Assessment:
        self._session.add(assessment)
        return assessment

    def delete(self, assessment: Assessment) -> None:
        self._session.delete(assessment)