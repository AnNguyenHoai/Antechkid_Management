"""Read-only one- or three-month tuition quote from immutable session allocations.

The quote is NOT a cash receipt or accrual posting. One Income is created only
by the existing authorized IncomeService; this code never posts three receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from centermanager.repositories.provider import (
    RepositoryProvider, create_default_repository_provider,
)
from centermanager.models.session import SessionStatus


@dataclass(frozen=True)
class MonthlyQuoteLine:
    month: date
    planned_sessions: int
    chargeable_sessions: int
    amount_vnd: int


@dataclass(frozen=True)
class MonthlyTuitionQuote:
    enrollment_id: int
    start_month: date
    month_count: int
    lines: tuple[MonthlyQuoteLine, ...]
    amount_vnd: int

    @property
    def payment_period(self) -> str:
        prefix = "TUITION_MONTH" if self.month_count == 1 else "TUITION_QUARTER"
        return f"{prefix}:{self.start_month.isoformat()}"


class MonthlyTuitionQuoteError(ValueError):
    pass


def _next_month(month: date, offset: int) -> date:
    total = month.year * 12 + month.month - 1 + offset
    return date(total // 12, total % 12 + 1, 1)


class MonthlyTuitionQuoteService:
    def __init__(self, session_factory, repository_provider: Optional[RepositoryProvider] = None):
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    def quote(self, enrollment_id: int, start_month: date, month_count: int):
        with self._session_factory() as db:
            return self.quote_in_session(db, enrollment_id, start_month, month_count)

    def quote_in_session(self, db, enrollment_id: int, start_month: date, month_count: int):
        if type(enrollment_id) is not int or enrollment_id <= 0:
            raise MonthlyTuitionQuoteError("Enrollment ID must be positive")
        if type(start_month) is not date or start_month.day != 1:
            raise MonthlyTuitionQuoteError("Quote must start on the first day of a month")
        if type(month_count) is not int or month_count not in (1, 3):
            raise MonthlyTuitionQuoteError("Select exactly one month or three consecutive months")
        repo = self._repository_provider.monthly_tuition(db)
        enrollment = repo.enrollment(enrollment_id)
        if enrollment is None or enrollment.class_id is None:
            raise MonthlyTuitionQuoteError("Enrollment not found")
        term = repo.term(enrollment_id)
        if term is None or start_month < term.effective_from:
            raise MonthlyTuitionQuoteError("Enrollment must activate monthly tuition first")
        if enrollment.status != "ACTIVE" or enrollment.reconciled_into_enrollment_id is not None:
            raise MonthlyTuitionQuoteError("Only an active canonical Enrollment can receive a future quote")
        requested_months = {_next_month(start_month, i) for i in range(month_count)}
        for period in repo.active_quoted_payment_periods(enrollment_id):
            if not period.startswith(("TUITION_MONTH:", "TUITION_QUARTER:")):
                continue
            try:
                kind, start = period.split(":", 1)
                paid_month = date.fromisoformat(start)
                if paid_month.day != 1 or kind not in ("TUITION_MONTH", "TUITION_QUARTER"):
                    raise ValueError("Malformed billing receipt")
                covers = {
                    _next_month(paid_month, i)
                    for i in range(1 if kind == "TUITION_MONTH" else 3)
                }
            except (ValueError, OverflowError) as exc:
                raise MonthlyTuitionQuoteError(
                    "Previous quoted Tuition receipt metadata must be reconciled"
                ) from exc
            if requested_months & covers:
                raise MonthlyTuitionQuoteError(
                    "An ACTIVE Tuition receipt already covers a requested month; "
                    "review/void the original before collecting again"
                )
        lines = []
        for offset in range(month_count):
            month = _next_month(start_month, offset)
            plan, allocations = repo.monthly_plan_allocations(enrollment.class_id, month)
            if plan is None or not allocations:
                raise MonthlyTuitionQuoteError(f"Activated tuition plan missing for {month.isoformat()}")
            if sum(item.amount_vnd for item in allocations) != plan.monthly_fee_vnd:
                raise MonthlyTuitionQuoteError("Incomplete immutable plan allocations")
            count = 0
            amount = 0
            for item in allocations:
                day = item.original_date
                if day.replace(day=1) != month:
                    raise MonthlyTuitionQuoteError("Plan allocation month mismatch")
                lesson = repo.teaching_session(item.session_id)
                if lesson is None or lesson.class_id != enrollment.class_id:
                    raise MonthlyTuitionQuoteError("Plan references a missing/foreign teaching session")
                if day < term.effective_from or (term.effective_until is not None and day > term.effective_until):
                    continue
                if enrollment.start_date is not None and day < enrollment.start_date:
                    continue
                if enrollment.end_date is not None and day > enrollment.end_date:
                    continue
                if enrollment.enrolled_from_session is not None and lesson.session_number < enrollment.enrolled_from_session:
                    continue
                if enrollment.withdrawn_from_session is not None and lesson.session_number >= enrollment.withdrawn_from_session:
                    continue
                count += 1
                latest = max(repo.outcomes_for_session(enrollment_id, lesson.id),
                             key=lambda e: e.revision, default=None)
                if lesson.status == SessionStatus.CANCELLED.value and latest is None:
                    raise MonthlyTuitionQuoteError("Cancelled lesson lacks an approved billing decision")
                if latest is not None and latest.outcome == "CENTRE_CANCELLED_NO_MAKEUP":
                    continue
                amount += int(item.amount_vnd)
            lines.append(MonthlyQuoteLine(month, len(allocations), count, amount))
        return MonthlyTuitionQuote(
            enrollment_id, start_month, month_count, tuple(lines),
            sum(line.amount_vnd for line in lines),
        )
