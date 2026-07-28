# -*- coding: utf-8 -*-
"""
StudentHighlightValidator - validation for highlight creation and updates.
"""
from typing import Optional

from centermanager.models.student_highlight import HighlightType
from centermanager.models.session import SessionStatus
from centermanager.repositories.enrollment_repository import EnrollmentRepository


class StudentHighlightValidator:
    @staticmethod
    def validate_type(highlight_type: str) -> str:
        valid = [e.value for e in HighlightType]
        if highlight_type not in valid:
            raise ValueError(f"Highlight type must be one of: {', '.join(valid)}")
        return highlight_type

    @staticmethod
    def validate_title(title: str) -> str:
        if not title or not title.strip():
            raise ValueError("Title is required.")
        return title.strip()

    @staticmethod
    def validate_student_in_class(
        session_factory,
        student_id: int,
        class_id: int,
    ) -> bool:
        """Check if student is enrolled in the class."""
        with session_factory() as db_session:
            repo = EnrollmentRepository(db_session)
            return repo.exists(student_id, class_id)

    @staticmethod
    def validate_session_completed(session) -> bool:
        """Check if session status is COMPLETED."""
        return session.status == SessionStatus.COMPLETED.value