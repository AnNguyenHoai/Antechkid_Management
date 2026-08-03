# -*- coding: utf-8 -*-
"""
OutstandingService - Business Rule Engine for tuition balance calculation.
Calculates expected tuition, paid amount, and outstanding balance.
Never stores data.
"""
import logging
from typing import List, Optional, Tuple, Dict

from sqlalchemy.orm import sessionmaker

from centermanager.dto.outstanding_dto import OutstandingDTO, StudentOutstandingSummary
from centermanager.repositories.student_repository import StudentRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.models.enrollment import Enrollment
from centermanager.models.income import Income

logger = logging.getLogger(__name__)


class OutstandingService:
    """
    Outstanding Tuition Engine.
    Read-only business rule engine.
    No database writes.
    """

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def _get_total_paid(self, student_id: int, class_id: int) -> int:
        """Calculate total paid amount for a student in a specific class."""
        with self._session_factory() as session:
            repo = IncomeRepository(session)
            incomes = repo.list_active(
                student_id=student_id,
                class_id=class_id,
                offset=0,
                limit=10000  # get all
            )
            total = sum(inc.amount for inc in incomes)
            return int(total)

    def get_outstanding_for_enrollment(
        self,
        student_id: int,
        class_id: int,
        enrollment: Optional[Enrollment] = None
    ) -> Optional[OutstandingDTO]:
        """
        Calculate outstanding for a specific student-class enrollment.
        Returns None if enrollment not found or class fee is not set.
        """
        with self._session_factory() as session:
            # Get enrollment
            if enrollment is None:
                enroll_repo = EnrollmentRepository(session)
                enrollment = session.query(Enrollment).filter(
                    Enrollment.student_id == student_id,
                    Enrollment.class_id == class_id
                ).first()
                if enrollment is None:
                    return None

            # Get class
            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is None or class_obj.fee is None or class_obj.fee == 0:
                # No fee defined, skip
                return None

            expected = class_obj.fee
            paid = self._get_total_paid(student_id, class_id)

            # Get student
            student_repo = StudentRepository(session)
            student = student_repo.get_by_id(student_id)
            if student is None:
                return None

            return OutstandingDTO.create(
                student_id=student_id,
                student_name=student.full_name,
                student_code=student.student_code,
                class_id=class_id,
                class_name=class_obj.name,
                expected_tuition=expected,
                paid=paid
            )

    def get_all_outstanding(
        self,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> Tuple[List[OutstandingDTO], int]:
        """
        Get outstanding for all active enrollments.
        Returns (list, total_count) for pagination.
        """
        with self._session_factory() as session:
            enroll_repo = EnrollmentRepository(session)
            query = session.query(Enrollment).filter(
                Enrollment.status == "active"  # or 'ACTIVE'
            )

            # Filter by class
            if class_id is not None:
                query = query.filter(Enrollment.class_id == class_id)

            # Filter by search text (student name/code)
            if search_text:
                from sqlalchemy import or_
                query = query.join(Enrollment.student).filter(
                    or_(
                        Student.full_name.ilike(f"%{search_text}%"),
                        Student.student_code.ilike(f"%{search_text}%")
                    )
                )

            total = query.count()
            enrollments = query.offset(offset).limit(limit).all()

            results = []
            for enrollment in enrollments:
                dto = self.get_outstanding_for_enrollment(
                    enrollment.student_id,
                    enrollment.class_id,
                    enrollment
                )
                if dto is not None:
                    # Apply status filter
                    if status_filter and dto.status != status_filter:
                        continue
                    results.append(dto)

            # Recalculate total after filters (simplified)
            return results, len(results)

    def get_student_summary(self, student_id: int) -> Optional[StudentOutstandingSummary]:
        """
        Get aggregated outstanding summary for a student across all classes.
        """
        with self._session_factory() as session:
            student_repo = StudentRepository(session)
            student = student_repo.get_by_id(student_id)
            if student is None:
                return None

            enroll_repo = EnrollmentRepository(session)
            enrollments = enroll_repo.get_by_student(student_id)

            details = []
            total_expected = 0
            total_paid = 0

            for enrollment in enrollments:
                if enrollment.class_id is None:
                    continue
                dto = self.get_outstanding_for_enrollment(
                    student_id,
                    enrollment.class_id,
                    enrollment
                )
                if dto is not None:
                    details.append(dto)
                    total_expected += dto.expected_tuition
                    total_paid += dto.paid

            total_outstanding = total_expected - total_paid
            if total_outstanding == 0:
                status = "Paid"
            elif total_outstanding > 0:
                status = "Partial"
            else:
                status = "Overpaid"

            return StudentOutstandingSummary(
                student_id=student_id,
                student_name=student.full_name,
                student_code=student.student_code,
                total_expected=total_expected,
                total_paid=total_paid,
                total_outstanding=total_outstanding,
                status=status,
                details=details
            )

    def get_outstanding_stats(self) -> Dict[str, int]:
        """
        Get summary statistics for the dashboard.
        """
        all_dtos, _ = self.get_all_outstanding(limit=10000)
        total_students = len(set(dto.student_id for dto in all_dtos))
        total_outstanding = sum(dto.outstanding for dto in all_dtos if dto.outstanding > 0)
        total_expected = sum(dto.expected_tuition for dto in all_dtos)
        total_paid = sum(dto.paid for dto in all_dtos)

        return {
            "total_students_with_debt": total_students,
            "total_outstanding": total_outstanding,
            "total_expected": total_expected,
            "total_paid": total_paid,
        }