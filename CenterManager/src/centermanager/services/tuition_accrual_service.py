"""Deterministic tuition accrual read model.

Accrual is derived from the immutable Enrollment tuition snapshot plus teaching
sessions. It is intentionally not persisted and has no accounting-period input.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Tuple

from centermanager.services.tuition_policy import BillableSessionPolicy


_MONEY_QUANTUM = Decimal("0.0001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class TuitionAccrualError(Exception):
    pass


class TuitionAccrualNotFoundError(TuitionAccrualError):
    pass


class TuitionAccrualUnresolvedError(TuitionAccrualError):
    pass


@dataclass(frozen=True)
class TuitionAccrualResult:
    enrollment_id: int
    as_of_date: date
    planned_sessions: int
    billable_sessions: int
    billable_session_numbers: Tuple[int, ...]
    unit_fee: Decimal
    gross_accrued: Decimal
    discount: Decimal
    net_accrued: Decimal
    contract_discount: Decimal


class TuitionAccrualService:
    """Calculate tuition obligation for one Enrollment as of a business date."""

    def __init__(self, session_factory: Callable, repository_provider) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider

    @staticmethod
    def _session_effective_date(session) -> date:
        """Completed-session date used by the as-of boundary.

        Prefer the actual delivery date. Legacy/completed rows without one fall
        back to their scheduled date, which is required by the Session model.
        """
        return getattr(session, "actual_date", None) or session.scheduled_date

    @classmethod
    def calculate_from_records(cls, enrollment, sessions, as_of_date: date) -> TuitionAccrualResult:
        """Pure calculation helper used by the repository-backed API and tests."""
        if not getattr(enrollment, "has_tuition_contract", False):
            raise TuitionAccrualUnresolvedError(
                "Enrollment tuition contract is unresolved; accrual cannot be calculated safely."
            )

        planned_sessions = int(enrollment.planned_sessions)
        unit_fee = _money(Decimal(enrollment.unit_fee))
        contract_discount = _money(Decimal(enrollment.discount_amount or 0))

        eligible = []
        for teaching_session in sessions:
            if cls._session_effective_date(teaching_session) > as_of_date:
                continue
            if BillableSessionPolicy.is_billable(teaching_session, enrollment):
                eligible.append(teaching_session)

        # Protect the read model from duplicate session objects supplied by a
        # custom repository/provider. Session number is unique per class.
        by_number = {int(item.session_number): item for item in eligible}
        session_numbers = tuple(sorted(by_number))
        billable_count = len(session_numbers)

        gross = _money(unit_fee * Decimal(billable_count))
        discount_accrued = _money(
            contract_discount * Decimal(billable_count) / Decimal(planned_sessions)
        )
        # Rounding must never make accrued discount exceed accrued gross.
        discount_accrued = min(discount_accrued, gross)
        net = _money(gross - discount_accrued)

        return TuitionAccrualResult(
            enrollment_id=int(enrollment.id),
            as_of_date=as_of_date,
            planned_sessions=planned_sessions,
            billable_sessions=billable_count,
            billable_session_numbers=session_numbers,
            unit_fee=unit_fee,
            gross_accrued=gross,
            discount=discount_accrued,
            net_accrued=net,
            contract_discount=contract_discount,
        )

    def calculate(self, enrollment_id: int, as_of_date: date) -> TuitionAccrualResult:
        if as_of_date is None:
            raise TuitionAccrualError("as_of_date is required.")

        with self._session_factory() as session:
            enrollment = self._repository_provider.enrollments(session).get_by_id(enrollment_id)
            if enrollment is None:
                raise TuitionAccrualNotFoundError(f"Enrollment {enrollment_id} not found.")
            if enrollment.class_id is None:
                raise TuitionAccrualUnresolvedError(
                    "Enrollment has no class identity; accrual cannot be calculated safely."
                )
            sessions = self._repository_provider.sessions(session).get_by_class(enrollment.class_id)
            return self.calculate_from_records(enrollment, sessions, as_of_date)
