# -*- coding: utf-8 -*-
"""
Enrollment repository - data access for Enrollment entity.
"""
from typing import Optional

from sqlalchemy.orm import Session

from centermanager.models.enrollment import Enrollment
from centermanager.repositories.base import BaseRepository


class EnrollmentRepository(BaseRepository[Enrollment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Enrollment)

    def exists(self, student_id: int, class_id: int) -> bool:
        """Check if a student is enrolled in a class."""
        return self._session.query(Enrollment).filter(
            Enrollment.student_id == student_id,
            Enrollment.class_id == class_id
        ).first() is not None