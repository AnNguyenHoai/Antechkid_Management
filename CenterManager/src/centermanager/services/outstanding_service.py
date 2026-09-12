# -*- coding: utf-8 -*-
"""
OutstandingService - Business Rule Engine for tuition balance calculation.
Calculates expected tuition, paid amount, and outstanding balance.
Never stores data.
"""
import logging
from typing import List, Optional, Tuple, Dict

from sqlalchemy.orm import sessionmaker

from centermanager.dto.outstanding_dto import (
    OutstandingDTO,
    StudentOutstandingSummary,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
)
from centermanager.repositories.enrollment_repository import EnrollmentRepository
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.models.enrollment import Enrollment

logger = logging.getLogger(__name__)


class OutstandingService:
    TUITION_INCOME_TYPE = "Tuition"
    NO_TUITION_CONFIGURED_STATUS = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
    """
    Outstanding Tuition Engine.
    Read-only business rule engine.
    No database writes.
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    def _get_total_paid(self, session, student_id: int, class_id: int) -> int:
        """Calculate only Tuition income paid for a student in a specific class."""
        repo = self._repository_provider.incomes(session)
        incomes = repo.list_active(
            student_id=student_id,
            class_id=class_id,
            income_type=self.TUITION_INCOME_TYPE,
            offset=0,
            limit=10000,
        )
        return int(sum(inc.amount for inc in incomes))

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
            enroll_repo = self._repository_provider.enrollments(session)
            if enrollment is None:
                enrollment = enroll_repo.get_by_student_and_class(student_id, class_id)
                enrollment = enrollment[0] if enrollment else None
                if enrollment is None:
                    logger.warning(f"No enrollment found for student {student_id}, class {class_id}")
                    return None

            class_repo = self._repository_provider.classes(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is None:
                logger.warning(f"Class {class_id} not found")
                return None
            configured = class_obj.fee is not None and class_obj.fee > 0
            expected = int(class_obj.fee) if configured else 0
            paid = self._get_total_paid(session, student_id, class_id)

            student_repo = self._repository_provider.students(session)
            student = student_repo.get_by_id(student_id)
            if student is None:
                logger.warning(f"Student {student_id} not found")
                return None

            return OutstandingDTO.create(
                student_id=student_id,
                student_name=student.full_name,
                student_code=student.student_code,
                class_id=class_id,
                class_name=class_obj.name,
                expected_tuition=expected,
                paid=paid,
                tuition_configured=configured,
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
            enroll_repo = self._repository_provider.enrollments(session)
            enrollments, total = enroll_repo.list_for_outstanding(
                class_id=class_id,
                search_text=search_text,
                offset=offset,
                limit=limit,
            )
            logger.debug(f"Found {len(enrollments)} enrollments (total {total})")

            results = []
            for enrollment in enrollments:
                dto = self.get_outstanding_for_enrollment(
                    enrollment.student_id,
                    enrollment.class_id,
                    enrollment
                )
                if dto is not None:
                    if status_filter and dto.status != status_filter:
                        continue
                    results.append(dto)

            # Preserve the historical API contract: status filtering is applied
            # after outstanding calculation, so the returned total is result count.
            return results, len(results)

    def get_student_summary(self, student_id: int) -> Optional[StudentOutstandingSummary]:
        """
        Get aggregated outstanding summary for a student across all classes.
        """
        with self._session_factory() as session:
            student_repo = self._repository_provider.students(session)
            student = student_repo.get_by_id(student_id)
            if student is None:
                logger.warning(f"Student {student_id} not found")
                return None

            enroll_repo = self._repository_provider.enrollments(session)
            enrollments = enroll_repo.get_by_student(student_id)

            details = []
            seen_pairs = set()
            seen_class_ids = set()
            total_expected = 0
            total_paid = 0
            has_unconfigured_tuition = False

            for enrollment in enrollments:
                pair = (enrollment.student_id, enrollment.class_id)
                if pair in seen_pairs or enrollment.class_id in seen_class_ids:
                    continue
                seen_pairs.add(pair)
                seen_class_ids.add(enrollment.class_id)
                if enrollment.class_id is None:
                    continue
                dto = self.get_outstanding_for_enrollment(
                    student_id,
                    enrollment.class_id,
                    enrollment
                )
                if dto is not None:
                    details.append(dto)
                    total_paid += dto.paid
                    if dto.tuition_configured:
                        total_expected += dto.expected_tuition
                    else:
                        has_unconfigured_tuition = True

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
