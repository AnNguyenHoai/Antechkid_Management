# -*- coding: utf-8 -*-
"""
Student repository with domain-specific queries.
"""
import re
from typing import Optional, List

from sqlalchemy.orm import Session

from centermanager.models.student import Student
from centermanager.repositories.base import BaseRepository


class StudentRepository(BaseRepository[Student]):
    """Repository for Student entity with domain-specific methods."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Student)

    def get_by_code(self, student_code: str) -> Optional[Student]:
        """Get a student by unique student_code (active only)."""
        return self._session.query(Student).filter(
            Student.student_code == student_code,
            Student.deleted_at.is_(None),
        ).first()

    def get_by_code_including_deleted(self, student_code: str) -> Optional[Student]:
        """Get a student by code regardless of deleted status."""
        return self._session.query(Student).filter(
            Student.student_code == student_code
        ).first()

    def get_by_id_including_deleted(self, student_id: int) -> Optional[Student]:
        """Get student by ID regardless of deleted status."""
        return self._session.get(Student, student_id)

    def list_active(self) -> List[Student]:
        """List active students (deleted_at IS NULL) ordered by student_code."""
        return self._session.query(Student).filter(
            Student.deleted_at.is_(None)
        ).order_by(Student.student_code).all()

    def list_all_including_deleted(self) -> List[Student]:
        """List all students including soft-deleted ones."""
        return self._session.query(Student).all()

    def get_all_student_codes(self) -> List[str]:
        """Return all student_code values (including deleted)."""
        results = self._session.query(Student.student_code).all()
        return [r[0] for r in results]

    def get_highest_hs_number(self) -> Optional[int]:
        """
        Find the highest numeric value from student codes matching pattern ^HS\\d+$.
        Returns None if no valid HS code exists.
        """
        # Use raw string for regex pattern to avoid escape warnings
        pattern = re.compile(r"^HS(\d+)$")
        all_codes = self.get_all_student_codes()
        max_num = None
        for code in all_codes:
            if code is None:
                continue
            match = pattern.match(code)
            if match:
                num = int(match.group(1))
                if max_num is None or num > max_num:
                    max_num = num
        return max_num