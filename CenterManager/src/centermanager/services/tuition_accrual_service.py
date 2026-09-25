"""Deterministic tuition accrual read model.

Accrual is derived from the immutable Enrollment tuition snapshot, its snapshotted
billing-policy version, teaching sessions, and optional attendance records. It is
intentionally not persisted and has no accounting-period input.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable, Mapping, Optional, Tuple

from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
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
    billing_policy_version: str


class TuitionAccrualService:
    """Calculate tuition obligation for one Enrollment as of a business date."""

    def __init__(
        self,
        session_factory: Callable,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    @staticmethod
    def _session_effective_date(session) -> date:
        """Completed-session date used by the as-of boundary."""
        return getattr(session, "actual_date", None) or session.scheduled_date

    @staticmethod
    def _attendance_map(attendances) -> dict[int, object]:
        """Build deterministic session->attendance map for one student."""
        return {
            int(item.session_id): item
            for item in attendances
            if getattr(item, "session_id", None) is not None
        }

    @classmethod
    def _attendance_from_sessions(cls, enrollment, sessions) -> dict[int, object]:
        """Resolve attendance already attached/lazy-loadable on Session records.

        This keeps existing composed read models (Outstanding and Tuition Detail)
        attendance-aware without moving policy arithmetic into those callers.
        Repository-backed ``calculate`` still supplies an explicit map.
        """
        result: dict[int, object] = {}
        student_id = getattr(enrollment, "student_id", None)
        if student_id is None:
            return result
        for teaching_session in sessions:
            session_id = getattr(teaching_session, "id", None)
            if session_id is None:
                continue
            for attendance in (getattr(teaching_session, "attendances", None) or []):
                if getattr(attendance, "student_id", None) == student_id:
                    result[int(session_id)] = attendance
                    break
        return result

    @classmethod
    def calculate_from_records(
        cls,
        enrollment,
        sessions,
        as_of_date: date,
        attendance_by_session_id: Optional[Mapping[int, object]] = None,
    ) -> TuitionAccrualResult:
        """Pure calculation helper used by repository-backed API and tests."""
        if not getattr(enrollment, "has_tuition_contract", False):
            raise TuitionAccrualUnresolvedError(
                "Enrollment tuition contract is unresolved; accrual cannot be calculated safely."
            )

        sessions = list(sessions)
        planned_sessions = int(enrollment.planned_sessions)
        unit_fee = _money(Decimal(enrollment.unit_fee))
        contract_discount = _money(Decimal(enrollment.discount_amount or 0))
        if attendance_by_session_id is None:
            attendance_by_session_id = cls._attendance_from_sessions(enrollment, sessions)

        eligible = []
        for teaching_session in sessions:
            if cls._session_effective_date(teaching_session) > as_of_date:
                continue
            attendance = attendance_by_session_id.get(
                getattr(teaching_session, "id", None)
            )
            if BillableSessionPolicy.is_billable(
                teaching_session,
                enrollment,
                attendance,
            ):
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
            billing_policy_version=BillableSessionPolicy.policy_version_for(enrollment),
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
            attendance_by_session_id = {}
            attendance_factory = getattr(self._repository_provider, "attendances", None)
            if callable(attendance_factory):
                attendance_rows = attendance_factory(session).get_by_student(
                    enrollment.student_id
                )
                attendance_by_session_id = self._attendance_map(attendance_rows)
            return self.calculate_from_records(
                enrollment,
                sessions,
                as_of_date,
                attendance_by_session_id=attendance_by_session_id,
            )
