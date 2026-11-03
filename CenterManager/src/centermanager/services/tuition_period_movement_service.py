"""Read-only, exact-Enrollment tuition receivables movement by accounting period.

A FinancePeriod is a date window only.  Outstanding remains a cumulative
Enrollment balance; movements are calculated as the difference of its two
canonical as-of snapshots plus the signed settlement event ledger.

This service never modifies Income, tuition adjustments, transfers, or DB.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from centermanager.services.outstanding_service import OutstandingService


ZERO = Decimal("0")


@dataclass(frozen=True)
class TuitionPeriodMovement:
    enrollment_id: int
    student_id: int
    student_code: str
    student_name: str
    class_id: int
    class_name: str
    configured: bool
    opening: Optional[Decimal]
    accrued: Optional[Decimal]
    received: Decimal
    adjustments: Decimal
    closing: Optional[Decimal]
    # Each signed amount is enrollment-specific; prepaid is NOT netted elsewhere.
    @property
    def reconciles(self) -> bool:
        return not self.configured or (
            self.opening + self.accrued - self.received - self.adjustments == self.closing
        )


@dataclass(frozen=True)
class TuitionPeriodReport:
    period_start: date
    period_end: date
    rows: tuple[TuitionPeriodMovement, ...]

    @property
    def totals(self):
        configured = tuple(item for item in self.rows if item.configured)
        return {
            "opening": sum((row.opening for row in configured), ZERO),
            "accrued": sum((row.accrued for row in configured), ZERO),
            "received": sum((row.received for row in self.rows), ZERO),
            "adjustments": sum((row.adjustments for row in self.rows), ZERO),
            "closing": sum((row.closing for row in configured), ZERO),
            "unconfigured": len(self.rows) - len(configured),
            # Track collectible debt and prepaid independently at end of period.
            "receivable": sum((max(row.closing, ZERO) for row in configured), ZERO),
            "prepaid": sum((max(-row.closing, ZERO) for row in configured), ZERO),
        }


class TuitionPeriodMovementService:
    """A read-only projection using the canonical tuition ledger and accrual rules."""

    def __init__(self, outstanding_service: OutstandingService):
        self._outstanding = outstanding_service

    def build(self, *, period_start: date, period_end: date,
              class_id: Optional[int] = None,
              student_id: Optional[int] = None) -> TuitionPeriodReport:
        if (not isinstance(period_start, date) or not isinstance(period_end, date)
                or isinstance(period_start, __import__("datetime").datetime)
                or isinstance(period_end, __import__("datetime").datetime)
                or period_start > period_end or period_start <= date.min):
            raise ValueError("A valid closed FinancePeriod with a preceding day is required")
        opening_date = period_start - timedelta(days=1)
        outstanding = self._outstanding
        provider = outstanding._repository_provider
        rows = []
        with outstanding._session_factory() as session:
            enrollments, _ = provider.enrollments(session).list_for_outstanding(
                class_id=class_id, student_id=student_id,
                period_start=None, period_end=None, limit=None,
            )
            income_repo = provider.incomes(session)
            read_components = getattr(income_repo, "list_active_tuition_settlement_components", None)
            if not callable(read_components):
                raise RuntimeError("Canonical signed tuition settlement components are required")
            seen = set()
            for enrollment in enrollments:
                if enrollment.id is None or enrollment.id in seen:
                    continue
                seen.add(enrollment.id)
                if enrollment.class_id is None:
                    continue
                student = enrollment.student or provider.students(session).get_by_id(enrollment.student_id)
                klass = enrollment.class_ or provider.classes(session).get_by_id(enrollment.class_id)
                if student is None or klass is None:
                    raise RuntimeError(f"Enrollment #{enrollment.id}: missing student/class identity")

                earned_before, configured_before = outstanding._calculate_accrued(
                    session, enrollment, as_of_date=opening_date,
                )
                earned_end, configured_end = outstanding._calculate_accrued(
                    session, enrollment, as_of_date=period_end,
                )
                configured = configured_before and configured_end
                # These include refunds, cash payments, credit adjustments and
                # transfers, all identified by exact Enrollment and effective date.
                components = tuple(read_components(int(enrollment.id), as_of_date=period_end))
                before_settled = ZERO
                income_movement = ZERO
                noncash_movement = ZERO
                end_settled = ZERO
                for component in components:
                    amount = Decimal(str(component.amount))
                    if component.effective_date > period_end:
                        raise RuntimeError("Settlement component after as-of cutoff")
                    end_settled += amount
                    if component.effective_date < period_start:
                        before_settled += amount
                    elif component.source == "INCOME":
                        income_movement += amount  # refunds are negative
                    elif component.source in {"TUITION_ADJUSTMENT", "ENROLLMENT_TRANSFER"}:
                        noncash_movement += amount
                    else:
                        raise RuntimeError("Unsupported tuition settlement component source")
                if end_settled != before_settled + income_movement + noncash_movement:
                    raise RuntimeError(f"Enrollment #{enrollment.id}: invalid ledger partition")

                # Fail rather than presenting an unknown tuition contract as zero debt.
                opening = earned_before - before_settled if configured else None
                accrued = earned_end - earned_before if configured else None
                closing = earned_end - end_settled if configured else None
                row = TuitionPeriodMovement(
                    enrollment_id=int(enrollment.id),
                    student_id=int(enrollment.student_id),
                    student_code=student.student_code or "",
                    student_name=student.full_name or "",
                    class_id=int(enrollment.class_id),
                    class_name=klass.name or "",
                    configured=configured,
                    opening=opening, accrued=accrued,
                    received=income_movement, adjustments=noncash_movement,
                    closing=closing,
                )
                if not row.reconciles:
                    raise RuntimeError(f"Enrollment #{enrollment.id}: movement reconciliation failed")
                # Keep contracts with balance or movement, including historical
                # closed/withdrawn Enrollment with unpaid credit or refund.
                if (not configured or opening or accrued or income_movement
                        or noncash_movement or closing):
                    rows.append(row)
        rows.sort(key=lambda r: (r.student_name.casefold(), r.class_name.casefold(), r.enrollment_id))
        return TuitionPeriodReport(period_start, period_end, tuple(rows))
