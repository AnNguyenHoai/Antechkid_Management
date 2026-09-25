# -*- coding: utf-8 -*-
"""Enrollment-centric tuition outstanding read model.

Outstanding is derived in real time as Enrollment tuition accrual minus ACTIVE
Tuition payments attributed to that same Enrollment. FinancePeriod is retained
only as optional reporting/filter context and never creates tuition obligation.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.dto.outstanding_dto import (
    BALANCE_STATE_NO_TUITION_CONFIGURED,
    BALANCE_STATE_OWED,
    BALANCE_STATE_PAID,
    BALANCE_STATE_PREPAID,
    OUTSTANDING_STATUS_NO_TUITION_CONFIGURED,
    OutstandingDTO,
    StudentOutstandingSummary,
)
from centermanager.models.enrollment import Enrollment
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)
from centermanager.services.tuition_accrual_service import (
    TuitionAccrualService,
    TuitionAccrualUnresolvedError,
)

logger = logging.getLogger(__name__)


class OutstandingService:
    """Read-only Enrollment balance projection for tuition receivables and credit."""

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
        "balance_state": lambda dto: dto.balance_state or "",
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
        """Resolve optional accounting report context."""
        target = period_start or on_date
        period_repo = self._repository_provider.finance_periods(session)
        config = period_repo.get_unique_effective(target)
        if config is None:
            return None
        resolved = FinancePeriodDefinition.resolved_for_configuration(config, target)
        if period_start is not None and resolved.period_start != period_start:
            raise ValueError(
                f"{period_start.isoformat()} is not a canonical FinancePeriod start; "
                f"resolved start is {resolved.period_start.isoformat()}."
            )
        return resolved.period_start, resolved.period_end

    @staticmethod
    def _overlaps_period(
        enrollment: Enrollment,
        period_start: Optional[date],
        period_end: Optional[date],
    ) -> bool:
        if period_start is None or period_end is None:
            return True
        if enrollment.start_date and enrollment.start_date > period_end:
            return False
        if enrollment.end_date and enrollment.end_date < period_start:
            return False
        return True

    @staticmethod
    def _amount(value) -> Decimal:
        return Decimal(str(value or 0))

    def _get_total_paid(
        self,
        session,
        enrollment_id: int,
        *,
        as_of_date: date,
    ) -> Decimal:
        repo = self._repository_provider.incomes(session)
        return self._amount(
            repo.sum_active_tuition_for_enrollment(
                enrollment_id,
                as_of_date=as_of_date,
            )
        )

    def _calculate_accrued(
        self,
        session,
        enrollment: Enrollment,
        *,
        as_of_date: date,
    ) -> Tuple[Decimal, bool]:
        if enrollment.class_id is None:
            return Decimal("0"), False
        sessions = self._repository_provider.sessions(session).get_by_class(
            enrollment.class_id
        )
        try:
            accrual = TuitionAccrualService.calculate_from_records(
                enrollment,
                sessions,
                as_of_date,
            )
        except TuitionAccrualUnresolvedError:
            return Decimal("0"), False
        return self._amount(accrual.net_accrued), True

    def _calculate_from_enrollment(
        self,
        session,
        enrollment: Enrollment,
        resolved_period_start: Optional[date] = None,
        resolved_period_end: Optional[date] = None,
        payment_totals=None,
        *,
        as_of_date: Optional[date] = None,
    ) -> Optional[OutstandingDTO]:
        """Build one signed balance row for one exact Enrollment."""
        del payment_totals
        if enrollment.id is None or enrollment.class_id is None:
            return None
        if not self._overlaps_period(
            enrollment,
            resolved_period_start,
            resolved_period_end,
        ):
            return None

        cutoff = as_of_date or get_clock().today()
        class_obj = enrollment.class_
        if class_obj is None:
            class_obj = self._repository_provider.classes(session).get_by_id(
                enrollment.class_id
            )
        if class_obj is None:
            logger.warning("Class %s not found", enrollment.class_id)
            return None

        student = enrollment.student
        if student is None:
            student = self._repository_provider.students(session).get_by_id(
                enrollment.student_id
            )
        if student is None:
            logger.warning("Student %s not found", enrollment.student_id)
            return None

        accrued, configured = self._calculate_accrued(
            session,
            enrollment,
            as_of_date=cutoff,
        )
        paid = self._get_total_paid(
            session,
            int(enrollment.id),
            as_of_date=cutoff,
        )
        return OutstandingDTO.create(
            student_id=enrollment.student_id,
            student_name=student.full_name,
            student_code=student.student_code,
            class_id=enrollment.class_id,
            class_name=class_obj.name,
            expected_tuition=accrued,
            paid=paid,
            tuition_configured=configured,
            period_start=resolved_period_start,
            period_end=resolved_period_end,
            course_name=enrollment.course_name or class_obj.course,
            enrollment_id=int(enrollment.id),
        )

    def _report_period_for_request(
        self,
        session,
        *,
        target_date: date,
        period_start: Optional[date],
    ) -> Tuple[Optional[date], Optional[date], bool]:
        period = self._resolve_period(session, target_date, period_start)
        if period is None:
            return None, None, period_start is None
        return period[0], period[1], True

    def get_outstanding_for_enrollment(
        self,
        student_id: int,
        class_id: int,
        enrollment: Optional[Enrollment] = None,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
        as_of_date: Optional[date] = None,
        enrollment_id: Optional[int] = None,
    ) -> Optional[OutstandingDTO]:
        target_date = on_date or get_clock().today()
        cutoff = as_of_date or target_date
        with self._session_factory() as session:
            report_start, report_end, report_valid = self._report_period_for_request(
                session,
                target_date=target_date,
                period_start=period_start,
            )
            if not report_valid:
                return None

            enrollment_repo = self._repository_provider.enrollments(session)
            if enrollment is None and enrollment_id is not None:
                enrollment = enrollment_repo.get_by_id(enrollment_id)
                if enrollment is None:
                    return None
                if enrollment.student_id != student_id or enrollment.class_id != class_id:
                    raise ValueError(
                        "Enrollment does not belong to the requested student/class."
                    )

            if enrollment is None:
                matches = enrollment_repo.get_by_student_and_class(student_id, class_id)
                if not matches:
                    return None
                if len(matches) > 1:
                    raise ValueError(
                        "Multiple Enrollment contracts match student/class; "
                        "enrollment_id is required."
                    )
                enrollment = matches[0]

            return self._calculate_from_enrollment(
                session,
                enrollment,
                report_start,
                report_end,
                as_of_date=cutoff,
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
        resolved_period_start: Optional[date],
        resolved_period_end: Optional[date],
        as_of_date: date,
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

        results: List[OutstandingDTO] = []
        seen_enrollment_ids = set()
        for enrollment in enrollments:
            if enrollment.id is None or enrollment.id in seen_enrollment_ids:
                continue
            seen_enrollment_ids.add(enrollment.id)
            dto = self._calculate_from_enrollment(
                session,
                enrollment,
                resolved_period_start,
                resolved_period_end,
                as_of_date=as_of_date,
            )
            if dto is None:
                continue
            if status_filter and status_filter not in (dto.status, dto.balance_state):
                continue
            results.append(dto)

        getter = self._SORT_GETTERS.get(sort_by, self._SORT_GETTERS["outstanding"])
        results.sort(key=getter, reverse=not ascending)
        return results

    @staticmethod
    def _stats_for_rows(rows: List[OutstandingDTO]) -> Dict[str, int]:
        """Aggregate debt and prepaid independently; never net credit against debt."""
        configured = [dto for dto in rows if dto.tuition_configured]
        return {
            "total_rows": len(rows),
            "total_students_with_debt": len(
                {dto.student_id for dto in configured if dto.balance_state == BALANCE_STATE_OWED}
            ),
            "total_students_with_prepaid": len(
                {dto.student_id for dto in configured if dto.balance_state == BALANCE_STATE_PREPAID}
            ),
            "total_outstanding": sum(
                (dto.debt_amount for dto in configured),
                Decimal("0"),
            ),
            "total_prepaid": sum(
                (dto.prepaid_amount for dto in configured),
                Decimal("0"),
            ),
            "total_expected": sum(
                (dto.expected_tuition for dto in configured),
                Decimal("0"),
            ),
            "total_paid": sum(
                (dto.paid for dto in rows),
                Decimal("0"),
            ),
            "total_unconfigured_tuition": sum(
                1 for dto in rows if not dto.tuition_configured
            ),
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
        as_of_date: Optional[date] = None,
    ) -> Tuple[List[OutstandingDTO], int, Dict[str, int]]:
        target_date = on_date or get_clock().today()
        cutoff = as_of_date or target_date
        with self._session_factory() as session:
            report_start, report_end, report_valid = self._report_period_for_request(
                session,
                target_date=target_date,
                period_start=period_start,
            )
            if not report_valid:
                return [], 0, self._stats_for_rows([])

            rows = self._collect_outstanding(
                session,
                class_id=class_id,
                status_filter=status_filter,
                search_text=search_text,
                course_name=course_name,
                student_id=student_id,
                resolved_period_start=report_start,
                resolved_period_end=report_end,
                as_of_date=cutoff,
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
        as_of_date: Optional[date] = None,
    ) -> Tuple[List[OutstandingDTO], int]:
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
            as_of_date=as_of_date,
        )
        return rows, total

    def list_outstanding_classes(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> List[Tuple[int, str]]:
        target_date = on_date or get_clock().today()
        with self._session_factory() as session:
            report_start, report_end, report_valid = self._report_period_for_request(
                session,
                target_date=target_date,
                period_start=period_start,
            )
            if not report_valid:
                return []
            enrollments, _ = self._repository_provider.enrollments(session).list_for_outstanding(
                period_start=report_start,
                period_end=report_end,
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
        as_of_date: Optional[date] = None,
    ) -> Optional[StudentOutstandingSummary]:
        rows, _, _ = self.get_outstanding_page(
            student_id=student_id,
            period_start=period_start,
            on_date=on_date,
            as_of_date=as_of_date,
            offset=0,
            limit=None,
            sort_by="class_name",
            ascending=True,
        )
        if not rows:
            with self._session_factory() as session:
                student = self._repository_provider.students(session).get_by_id(student_id)
                if student is None:
                    return None
                student_name = student.full_name
                student_code = student.student_code
        else:
            student_name = rows[0].student_name
            student_code = rows[0].student_code

        total_expected = Decimal("0")
        total_paid = Decimal("0")
        has_unconfigured_tuition = False
        details: List[OutstandingDTO] = []
        seen_enrollment_ids = set()
        configured_count = 0
        for dto in rows:
            identity = dto.enrollment_id
            if identity is not None and identity in seen_enrollment_ids:
                continue
            if identity is not None:
                seen_enrollment_ids.add(identity)
            total_paid += self._amount(dto.paid)
            if dto.tuition_configured:
                configured_count += 1
                total_expected += self._amount(dto.expected_tuition)
            else:
                has_unconfigured_tuition = True
            details.append(dto)

        total_outstanding = total_expected - total_paid
        if has_unconfigured_tuition and configured_count == 0:
            balance_state = BALANCE_STATE_NO_TUITION_CONFIGURED
            status = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
        elif total_outstanding > 0:
            balance_state = BALANCE_STATE_OWED
            status = "Not Yet" if total_paid == 0 else "Partial"
        elif total_outstanding == 0:
            balance_state = BALANCE_STATE_PAID
            status = "Paid"
        else:
            balance_state = BALANCE_STATE_PREPAID
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
            balance_state=balance_state,
        )

    def get_outstanding_stats(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        search_text: Optional[str] = None,
        as_of_date: Optional[date] = None,
    ) -> Dict[str, int]:
        _, _, stats = self.get_outstanding_page(
            class_id=class_id,
            status_filter=status_filter,
            search_text=search_text,
            period_start=period_start,
            on_date=on_date,
            as_of_date=as_of_date,
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
        as_of_date: Optional[date] = None,
    ) -> str:
        rows, _, _ = self.get_outstanding_page(
            class_id=class_id,
            status_filter=status_filter,
            search_text=search_text,
            course_name=course_name,
            student_id=student_id,
            period_start=period_start,
            on_date=on_date,
            as_of_date=as_of_date,
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
                "Prepaid Credit",
                "Balance State",
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
                    row.prepaid_amount if row.tuition_configured else "",
                    row.balance_state,
                    row.status,
                    row.period_start.isoformat() if row.period_start else "",
                    row.period_end.isoformat() if row.period_end else "",
                ]
            )
        return output.getvalue()
