# -*- coding: utf-8 -*-
"""
StudentFilterService - applies advanced filters to student list.
"""
from typing import List
from datetime import date

from sqlalchemy.orm import sessionmaker

from centermanager.dto.student_filter_dto import StudentFilter
from centermanager.models.student import Student
from centermanager.models.enrollment import Enrollment
from centermanager.models.assessment import Assessment
from centermanager.models.class_ import Class
from centermanager.repositories.student_repository import StudentRepository


class StudentFilterService:
    """Service to filter students based on various criteria."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def filter_students(self, filter_criteria: StudentFilter) -> List[Student]:
        """Apply filters and return matching active students."""
        with self._session_factory() as session:
            q = session.query(Student).filter(Student.deleted_at.is_(None))

            # Archive is a lifecycle status. Soft-deleted students are already
            # excluded by the base query above.
            if filter_criteria.status == "ARCHIVED":
                q = q.filter(Student.status == "ARCHIVED")
            elif filter_criteria.status == "ACTIVE":
                q = q.filter(Student.status == "ACTIVE")

            # Enrollment status
            if filter_criteria.enrollment_status == "enrolled":
                q = q.join(Student.enrollments).filter(Enrollment.status == "active")
            elif filter_criteria.enrollment_status == "not_enrolled":
                q = q.outerjoin(Student.enrollments).filter(Enrollment.id.is_(None))

            # Assessment status
            if filter_criteria.assessment_status == "has_assessment":
                q = q.join(Student.assessments).distinct()
            elif filter_criteria.assessment_status == "no_assessment":
                q = q.outerjoin(Student.assessments).filter(Assessment.id.is_(None))

            # Class name
            if filter_criteria.class_name:
                q = q.join(Student.enrollments).join(Enrollment.class_).filter(
                    Class.name == filter_criteria.class_name
                )

            students = q.all()

            # Age filtering (in memory because SQLite date arithmetic is limited)
            if filter_criteria.age_min is not None or filter_criteria.age_max is not None:
                today = date.today()
                filtered = []
                for s in students:
                    if s.date_of_birth:
                        age = today.year - s.date_of_birth.year - (
                            (today.month, today.day) < (s.date_of_birth.month, s.date_of_birth.day)
                        )
                        if filter_criteria.age_min is not None and age < filter_criteria.age_min:
                            continue
                        if filter_criteria.age_max is not None and age > filter_criteria.age_max:
                            continue
                    else:
                        # If no DOB, include only if no age filter specified
                        if filter_criteria.age_min is not None or filter_criteria.age_max is not None:
                            continue
                    filtered.append(s)
                return filtered

            return students