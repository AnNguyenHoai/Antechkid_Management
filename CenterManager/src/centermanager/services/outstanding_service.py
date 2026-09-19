# -*- coding: utf-8 -*-
"""
OutstandingService - period-aware, read-only tuition balance read model.

Outstanding is derived in real time from enrollment obligations and valid ACTIVE
Tuition Income. It is never persisted. Filtering on calculated status is applied
before pagination so page totals are correct.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.dto.outstanding_dto import (
    OutstandingDTO,
    StudentOutstandingSummary,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
)
from centermanager.models.enrollment import Enrollment
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)

logger = logging.getLogger(__name__)


class OutstandingService:
    TUITION_INCOME_TYPE = "Tuition"
    NO_TUITION_CONFIGURED_STATUS = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED

    _SORT_GETTERS = {
        "student_code": lambda dto: dto.student_code or "",
        "student_name": lambda dto: (dto.student_name or "").casefold(),
        "class_name": lambda dto: (dto.class_name or "").casefold(),
        "expected_tuition": lambda dto: dto.expected_tuition,
        "paid": lambda dto: dto.paid,
        "outstanding": lambda dto: dto.outstanding,
        "status": lambda dto: dto.status or "",
    }

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    def _resolve_period(
        self,
        session,
        on_date: date,
        period_start: Optional[date] = None,
    ) -> Optional[Tuple[date, date]]:
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
        """Calculate valid Tuition income for one student/class/Finance period."""
        repo = self._repository_provider.incomes(session)
        total = repo.count_active(
            student_id=student_id,
            class_id=class_id,
            income_type=self.TUITION_INCOME_TYPE,
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
        )
        if total <= 0:
            return 0
        incomes = repo.list_active(
            student_id=student_id,
            class_id=class_id,
            income_type=self.TUITION_INCOME_TYPE,
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
            offset=0,
            limit=total,
        )
        return int(sum(inc.amount for inc in incomes))

    def _load_payment_totals(
        self,
        session,
        period_start: date,
        period_end: date,
    ) -> Dict[Tuple[int, int], int]:
        """Load all valid Tuition income once and group by student/class.

        The income repository active-list boundary is the canonical live-money
        source, so VOIDED and soft-deleted Income are excluded automatically.
        """
        repo = self._repository_provider.incomes(session)
        total = repo.count_active(
            income_type=self.TUITION_INCOME_TYPE,
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
        )
        if total <= 0:
            return {}
        incomes = repo.list_active(
            income_type=self.TUITION_INCOME_TYPE,
            finance_period_start=period_start,
            date_from=period_start,
            date_to=period_end,
            offset=0,
            limit=total,
        )
        grouped: Dict[Tuple[int, int], int] = {}
        for income in incomes:
            if income.student_id is None or income.class_id is None:
                continue
            key = (income.student_id, income.class_id)
            grouped[key] = grouped.get(key, 0) + int(income.amount)
        return grouped

    def _calculate_from_enrollment(
        self,
        session,
        enrollment: Enrollment,
        resolved_period_start: date,
        resolved_period_end: date,
        payment_totals: Optional[Dict[Tuple[int, int], int]] = None,
    ) -> Optional[OutstandingDTO]:
        if enrollment.class_id is None:
            return None
        if enrollment.start_date and enrollment.start_date > resolved_period_end:
            return None
        if enrollment.end_date and enrollment.end_date < resolved_period_start:
            return None

        class_obj = enrollment.class_
        if class_obj is None:
            class_repo = self._repository_provider.classes(session)
            class_obj = class_repo.get_by_id(enrollment.class_id)
        if class_obj is None:
            logger.warning("Class %s not found", enrollment.class_id)
            return None

        student = enrollment.student
        if student is None:
            student_repo = self._repository_provider.students(session)
            student = student_repo.get_by_id(enrollment.student_id)
        if student is None:
            logger.warning("Student %s not found", enrollment.student_id)
            return None

        configured = class_obj.fee is not None and class_obj.fee > 0
        expected = int(class_obj.fee) if configured else 0
        key = (enrollment.student_id, enrollment.class_id)
        if payment_totals is None:
            paid = self._get_total_paid(
                session,
                enrollment.student_id,
                enrollment.class_id,
                resolved_period_start,
                resolved_period_end,
            )
        else:
            paid = payment_totals.get(key, 0)

        return OutstandingDTO.create(
            student_id=enrollment.student_id,
            student_name=student.full_name,
            student_code=student.student_code,
            class_id=enrollment.class_id,
            class_name=class_obj.name,
            expected_tuition=expected,
            paid=paid,
            tuition_configured=configured,
            period_start=resolved_period_start,
            period_end=resolved_period_end,
            course_name=enrollment.course_name or class_obj.course,
        )

    def get_outstanding_for_enrollment(
        self,
        student_id: int,
        class_id: int,
        enrollment: Optional[Enrollment] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Optional[OutstandingDTO]:
        """Calculate outstanding for one student-class enrollment."""
        target_date = on_date or date.today()
        with self._session_factory() as session:
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                logger.warning(
                    "No Finance period configuration covers %s",
                    period_start or target_date,
                )
                return None
            resolved_period_start, resolved_period_end = period

            if enrollment is None:
                enrollment_repo = self._repository_provider.enrollments(session)
                matches = enrollment_repo.get_by_student_and_class(student_id, class_id)
                enrollment = matches[0] if matches else None
                if enrollment is None:
                    logger.warning(
                        "No enrollment found for student %s / class %s",
                        student_id,
                        class_id,
                    )
                    return None

            return self._calculate_from_enrollment(
                session,
                enrollment,
                resolved_period_start,
                resolved_period_end,
            )

    def _collect_outstanding(
        self,
        session,
        *,
        class_id: Optional[int],
        status_filter: Optional[str],
        search_text: Optional[str],
        course_name: Optional[str],
        student_id: Optional[int],
        resolved_period_start: date,
        resolved_period_end: date,
        sort_by: str,
        ascending: bool,
    ) -> List[OutstandingDTO]:
        enrollment_repo = self._repository_provider.enrollments(session)
        enrollments, _ = enrollment_repo.list_for_outstanding(
            class_id=class_id,
            course_name=course_name,
            student_id=student_id,
            period_start=resolved_period_start,
            period_end=resolved_period_end,
            search_text=search_text,
            offset=0,
            limit=None,
        )
        payment_totals = self._load_payment_totals(
            session, resolved_period_start, resolved_period_end
        )

        results: List[OutstandingDTO] = []
        seen_pairs = set()
        for enrollment in enrollments:
            key = (enrollment.student_id, enrollment.class_id)
            # Historical re-enrollment rows must not create duplicate debt for
            # the same student/class in a single Finance period.
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            dto = self._calculate_from_enrollment(
                session,
                enrollment,
                resolved_period_start,
                resolved_period_end,
                payment_totals=payment_totals,
            )
            if dto is None:
                continue
            if status_filter and dto.status != status_filter:
                continue
            results.append(dto)

        getter = self._SORT_GETTERS.get(sort_by, self._SORT_GETTERS["outstanding"])
        results.sort(key=getter, reverse=not ascending)
        return results

    @staticmethod
    def _stats_for_rows(rows: List[OutstandingDTO]) -> Dict[str, int]:
        all_dtos = rows
        configured = [dto for dto in all_dtos if dto.tuition_configured]
        total_unconfigured_tuition = sum(1 for dto in all_dtos if not dto.tuition_configured)
        return {
            "total_rows": len(all_dtos),
            "total_students_with_debt": len(
                {dto.student_id for dto in configured if dto.outstanding > 0}
            ),
            "total_outstanding": sum(
                max(dto.outstanding, 0) for dto in configured
            ),
            "total_expected": sum(dto.expected_tuition for dto in configured),
            "total_paid": sum(dto.paid for dto in all_dtos),
            "total_unconfigured_tuition": total_unconfigured_tuition,
        }

    def get_outstanding_page(
        self,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = 100,
        course_name: Optional[str] = None,
        student_id: Optional[int] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
        sort_by: str = "outstanding",
        ascending: bool = False,
    ) -> Tuple[List[OutstandingDTO], int, Dict[str, int]]:
        """Return a correct server page plus full-filter KPI totals.

        Status is a derived value, therefore status filtering is intentionally
        completed before offset/limit are applied.
        """
        target_date = on_date or date.today()
        with self._session_factory() as session:
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                return [], 0, self._stats_for_rows([])
            resolved_period_start, resolved_period_end = period
            rows = self._collect_outstanding(
                session,
                class_id=class_id,
                status_filter=status_filter,
                search_text=search_text,
                course_name=course_name,
                student_id=student_id,
                resolved_period_start=resolved_period_start,
                resolved_period_end=resolved_period_end,
                sort_by=sort_by,
                ascending=ascending,
            )
            total = len(rows)
            stats = self._stats_for_rows(rows)
            start = max(0, offset)
            if limit is None:
                page_rows = rows[start:]
            else:
                page_rows = rows[start : start + max(1, limit)]
            return page_rows, total, stats

    def get_all_outstanding(
        self,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = 100,
        course_name: Optional[str] = None,
        student_id: Optional[int] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
        sort_by: str = "outstanding",
        ascending: bool = False,
    ) -> Tuple[List[OutstandingDTO], int]:
        """Backward-compatible list API with correct derived pagination."""
        rows, total, _ = self.get_outstanding_page(
            class_id=class_id,
            status_filter=status_filter,
            search_text=search_text,
            offset=offset,
            limit=limit,
            course_name=course_name,
            student_id=student_id,
            period_start=period_start,
            on_date=on_date,
            sort_by=sort_by,
            ascending=ascending,
        )
        return rows, total

    def list_outstanding_classes(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> List[Tuple[int, str]]:
        """Return classes participating in the selected Finance period."""
        target_date = on_date or date.today()
        with self._session_factory() as session:
            period = self._resolve_period(session, target_date, period_start)
            if period is None:
                return []
            resolved_period_start, resolved_period_end = period
            enrollment_repo = self._repository_provider.enrollments(session)
            enrollments, _ = enrollment_repo.list_for_outstanding(
                period_start=resolved_period_start,
                period_end=resolved_period_end,
                offset=0,
                limit=None,
            )
            classes = {}
            for enrollment in enrollments:
                if enrollment.class_id is None:
                    continue
                class_name = (
                    enrollment.class_.name
                    if enrollment.class_ is not None
                    else enrollment.class_name
                )
                classes[enrollment.class_id] = class_name or f"Class #{enrollment.class_id}"
            return sorted(classes.items(), key=lambda item: item[1].casefold())

    def get_student_summary(
        self,
        student_id: int,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> Optional[StudentOutstandingSummary]:
        """Get aggregated outstanding summary for a student in one Finance period."""
        rows, _, _ = self.get_outstanding_page(
            student_id=student_id,
            period_start=period_start,
            on_date=on_date,
            offset=0,
            limit=None,
            sort_by="class_name",
            ascending=True,
        )
        if not rows:
            # Preserve the previous distinction between unknown student and an
            # enrolled student with no row by checking the student repository.
            with self._session_factory() as session:
                student_repo = self._repository_provider.students(session)
                student = student_repo.get_by_id(student_id)
                if student is None:
                    return None
                student_name = student.full_name
                student_code = student.student_code
        else:
            student_name = rows[0].student_name
            student_code = rows[0].student_code

        total_expected = 0
        total_paid = 0
        has_unconfigured_tuition = False
        details: List[OutstandingDTO] = []
        seen_class_ids = set()
        for dto in rows:
            # _collect_outstanding already deduplicates (student, class) pairs;
            # keep this guard as a compatibility/safety boundary for summaries.
            if dto.class_id in seen_class_ids:
                continue
            seen_class_ids.add(dto.class_id)
            total_paid += dto.paid
            if dto.tuition_configured:
                total_expected += dto.expected_tuition
            else:
                has_unconfigured_tuition = True
            details.append(dto)

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
            student_name=student_name,
            student_code=student_code,
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
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
    ) -> Dict[str, int]:
        """Get full-filter statistics for the selected Finance period."""
        _, _, stats = self.get_outstanding_page(
            class_id=class_id,
            status_filter=status_filter,
            search_text=search_text,
            period_start=period_start,
            on_date=on_date,
            offset=0,
            limit=1,
        )
        return stats

    def export_outstanding_csv(
        self,
        *,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        course_name: Optional[str] = None,
        student_id: Optional[int] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
        sort_by: str = "outstanding",
        ascending: bool = False,
    ) -> str:
        """Export every row matching the current read-only workspace filters."""
        rows, _, _ = self.get_outstanding_page(
            class_id=class_id,
            status_filter=status_filter,
            search_text=search_text,
            course_name=course_name,
            student_id=student_id,
            period_start=period_start,
            on_date=on_date,
            offset=0,
            limit=None,
            sort_by=sort_by,
            ascending=ascending,
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "Student Code",
                "Student",
                "Class",
                "Course",
                "Expected Tuition",
                "Paid",
                "Outstanding",
                "Status",
                "Finance Period Start",
                "Finance Period End",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.student_code,
                    row.student_name,
                    row.class_name,
                    row.course_name or "",
                    row.expected_tuition if row.tuition_configured else "",
                    row.paid,
                    row.outstanding if row.tuition_configured else "",
                    row.status,
                    row.period_start.isoformat() if row.period_start else "",
                    row.period_end.isoformat() if row.period_end else "",
                ]
            )
        return output.getvalue()
