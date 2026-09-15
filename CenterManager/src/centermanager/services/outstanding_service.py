# -*- coding: utf-8 -*-
"""
OutstandingService - period-aware business rule engine for tuition balance calculation.
Calculates expected tuition, paid amount, and outstanding balance for a Finance period.
Never stores data.
"""
import logging
from datetime import date
from typing import List, Optional, Tuple, Dict

from sqlalchemy.orm import sessionmaker

from centermanager.dto.outstanding_dto import (
    OutstandingDTO,
    StudentOutstandingSummary,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
)
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.models.enrollment import Enrollment
from centermanager.models.finance_period import FinancePeriodDefinition

logger = logging.getLogger(__name__)


class OutstandingService:
    TUITION_INCOME_TYPE = "Tuition"
    NO_TUITION_CONFIGURED_STATUS = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED

    def __init__(self, session_factory: sessionmaker, repository_provider: Optional[RepositoryProvider] = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    def _resolve_period(self, session, on_date: date, period_start: Optional[date] = None) -> Optional[Tuple[date, date]]:
        period_repo = self._repository_provider.finance_periods(session)
        if period_start is not None:
            config = period_repo.get_active(period_start)
            if config is None:
                return None
            return FinancePeriodDefinition.period_for_date(
                config.effective_from,
                period_start,
                config.duration_months,
            )

        config = period_repo.get_active(on_date)
        if config is None:
            return None
        return FinancePeriodDefinition.period_for_date(
            config.effective_from,
            on_date,
            config.duration_months,
        )

    def _get_total_paid(
        self,
        session,
        student_id: int,
        class_id: int,
        period_start: date,
        period_end: date,
    ) -> int:
        """Calculate Tuition income paid by the student/class in one Finance period."""
        repo = self._repository_provider.incomes(session)
        incomes = repo.list_active(
            student_id=student_id,
            class_id=class_id,
            income_type=self.TUITION_INCOME_TYPE,
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
            offset=0,
            limit=10000,
        )
        return int(sum(inc.amount for inc in incomes))

    def get_outstanding_for_enrollment(
        self,
        student_id: int,
        class_id: int,
        enrollment: Optional[Enrollment] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Optional[OutstandingDTO]:
        """Calculate outstanding for a student-class enrollment in one Finance period."""
        target_date = on_date or date.today()
        with self._session_factory() as session:
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                logger.warning("No Finance period configuration covers %s", period_start or target_date)
                return None
            resolved_period_start, resolved_period_end = period

            enroll_repo = self._repository_provider.enrollments(session)
            if enrollment is None:
                matches = enroll_repo.get_by_student_and_class(student_id, class_id)
                enrollment = matches[0] if matches else None
                if enrollment is None:
                    logger.warning(f"No enrollment found for student {student_id}")
                    return None

            if enrollment.start_date and enrollment.start_date > resolved_period_end:
                return None
            if enrollment.end_date and enrollment.end_date < resolved_period_start:
                return None

            class_repo = self._repository_provider.classes(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is None:
                logger.warning(f"Class {class_id} not found")
                return None
            configured = class_obj.fee is not None and class_obj.fee > 0
            expected = int(class_obj.fee) if configured else 0
            paid = self._get_total_paid(
                session,
                student_id,
                class_id,
                resolved_period_start,
                resolved_period_end,
            )

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
                period_start=resolved_period_start,
                period_end=resolved_period_end,
                course_name=enrollment.course_name or class_obj.course,
            )

    def get_all_outstanding(
        self,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: int = 100,
        course_name: Optional[str] = None,
        student_id: Optional[int] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Tuple[List[OutstandingDTO], int]:
        """Get period-aware outstanding rows with class/course/student/status filters."""
        target_date = on_date or date.today()
        with self._session_factory() as session:
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                return [], 0
            resolved_period_start, resolved_period_end = period
            enroll_repo = self._repository_provider.enrollments(session)
            enrollments, _ = enroll_repo.list_for_outstanding(
                class_id=class_id,
                course_name=course_name,
                student_id=student_id,
                period_start=resolved_period_start,
                period_end=resolved_period_end,
                search_text=search_text,
                offset=offset,
                limit=limit,
            )
            results = []
            for enrollment in enrollments:
                dto = self.get_outstanding_for_enrollment(
                    enrollment.student_id,
                    enrollment.class_id,
                    enrollment,
                    period_start=resolved_period_start,
                    on_date=target_date,
                )
                if dto is not None and (not status_filter or dto.status == status_filter):
                    results.append(dto)
            return results, len(results)

    def get_student_summary(
        self,
        student_id: int,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Optional[StudentOutstandingSummary]:
        """Get aggregated outstanding summary for a student in one Finance period."""
        with self._session_factory() as session:
            target_date = on_date or date.today()
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                return None
            resolved_period_start, resolved_period_end = period

            student_repo = self._repository_provider.students(session)
            student = student_repo.get_by_id(student_id)
            if student is None:
                logger.warning(f"Student {student_id} not found")
                return None

            enroll_repo = self._repository_provider.enrollments(session)
            enrollments, _ = enroll_repo.list_for_outstanding(
                student_id=student_id,
                period_start=resolved_period_start,
                period_end=resolved_period_end,
                offset=0,
                limit=10000,
            )
            details = []
            seen_pairs = set()
            total_expected = 0
            total_paid = 0
            has_unconfigured_tuition = False

            for enrollment in enrollments:
                pair = (enrollment.student_id, enrollment.class_id)
                if pair in seen_pairs or enrollment.class_id is None:
                    continue
                seen_pairs.add(pair)
                dto = self.get_outstanding_for_enrollment(
                    student_id,
                    enrollment.class_id,
                    enrollment,
                    period_start=resolved_period_start,
                    on_date=target_date,
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
            elif total_outstanding > 0 and total_paid == 0:
                status = "Not Yet"
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
                details=details,
                has_unconfigured_tuition=has_unconfigured_tuition,
            )

    def get_outstanding_stats(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Dict[str, int]:
        """Get summary statistics for a selected Finance period."""
        all_dtos, _ = self.get_all_outstanding(
            period_start=period_start,
            on_date=on_date,
            limit=10000,
        )
        total_students = len(set(dto.student_id for dto in all_dtos if dto.outstanding > 0))
        total_outstanding = sum(dto.outstanding for dto in all_dtos if dto.outstanding > 0)
        total_expected = sum(dto.expected_tuition for dto in all_dtos)
        total_paid = sum(dto.paid for dto in all_dtos)
        return {
            "total_students_with_debt": total_students,
            "total_outstanding": total_outstanding,
            "total_expected": total_expected,
            "total_paid": total_paid,
        }
