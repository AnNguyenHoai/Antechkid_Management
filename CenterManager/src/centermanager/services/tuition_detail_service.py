# -*- coding: utf-8 -*-
"""Read-only, explainable tuition detail projection for one Enrollment.

TUITION-10 deliberately composes the canonical TuitionAccrualService and
Enrollment-attributed Income rows. It does not persist tuition state and it does
not use FinancePeriod to create or limit tuition obligations.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.dto.outstanding_dto import OutstandingDTO
from centermanager.models.income import Income
from centermanager.models.session import SessionStatus
from centermanager.repositories.provider import (
    RepositoryProvider,
    create_default_repository_provider,
)
from centermanager.services.tuition_accrual_service import (
    TuitionAccrualService,
    TuitionAccrualUnresolvedError,
)


@dataclass(frozen=True)
class TuitionSessionDetail:
    session_number: int
    title: str
    status: str
    scheduled_date: date
    actual_date: Optional[date]
    effective_date: date
    billable: bool
    billing_contribution: Decimal
    explanation: str


@dataclass(frozen=True)
class TuitionPaymentDetail:
    income_id: int
    payment_date: date
    amount: Decimal
    wallet: str
    payment_period: Optional[str]
    finance_period_start: Optional[date]
    received_by: Optional[str]
    note: Optional[str]

    @property
    def accounting_reference(self) -> str:
        period = (
            self.finance_period_start.isoformat()
            if self.finance_period_start is not None
            else "unassigned"
        )
        return f"Income #{self.income_id} · FinancePeriod {period}"


@dataclass(frozen=True)
class TuitionDetailReadModel:
    enrollment_id: int
    student_id: int
    student_name: str
    student_code: str
    class_id: int
    class_name: str
    course_name: Optional[str]
    as_of_date: date
    tuition_configured: bool
    agreed_course_fee: Optional[Decimal]
    planned_sessions: Optional[int]
    enrolled_from_session: Optional[int]
    enrolled_until_session: Optional[int]
    unit_fee: Optional[Decimal]
    contract_discount: Decimal
    completed_sessions: int
    billable_sessions: int
    gross_accrued: Decimal
    recognized_discount: Decimal
    net_accrued: Decimal
    paid: Decimal
    balance: Decimal
    balance_state: str
    status: str
    debt_amount: Decimal
    prepaid_amount: Decimal
    sessions: Tuple[TuitionSessionDetail, ...]
    payments: Tuple[TuitionPaymentDetail, ...]


class TuitionDetailNotFoundError(LookupError):
    pass


class TuitionDetailService:
    """Build an auditable Student + Enrollment tuition detail projection."""

    TUITION_INCOME_TYPE = "Tuition"

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = (
            repository_provider or create_default_repository_provider()
        )

    @classmethod
    def from_outstanding_service(cls, outstanding_service) -> "TuitionDetailService":
        """Reuse the Finance composition root without giving Qt repository access."""
        session_factory = getattr(outstanding_service, "_session_factory", None)
        provider = getattr(outstanding_service, "_repository_provider", None)
        if session_factory is None:
            raise ValueError("OutstandingService does not expose its application session factory.")
        return cls(session_factory, provider)

    @staticmethod
    def _amount(value) -> Decimal:
        return Decimal(str(value or 0))

    @staticmethod
    def _effective_date(session) -> date:
        return session.actual_date or session.scheduled_date

    @classmethod
    def _session_rows(
        cls,
        enrollment,
        sessions,
        *,
        as_of_date: date,
        billable_numbers,
        unit_fee: Decimal,
    ) -> Tuple[TuitionSessionDetail, ...]:
        start = enrollment.enrolled_from_session
        end = enrollment.enrolled_until_session
        billable_set = set(billable_numbers)
        rows: List[TuitionSessionDetail] = []
        for teaching_session in sorted(
            sessions, key=lambda item: (item.session_number, item.id or 0)
        ):
            number = teaching_session.session_number
            if start is not None and number < start:
                continue
            if end is not None and number > end:
                continue
            effective_date = cls._effective_date(teaching_session)
            billable = number in billable_set
            if effective_date > as_of_date:
                explanation = "Sau ngày chốt"
            elif teaching_session.status != SessionStatus.COMPLETED.value:
                explanation = f"Không tính phí: {teaching_session.status}"
            elif not enrollment.has_tuition_contract:
                explanation = "Chưa có snapshot học phí"
            elif billable:
                explanation = "Đã hoàn thành · tính phí"
            else:
                explanation = "Không thuộc phạm vi tính phí"
            rows.append(
                TuitionSessionDetail(
                    session_number=number,
                    title=teaching_session.title or f"Buổi {number}",
                    status=teaching_session.status,
                    scheduled_date=teaching_session.scheduled_date,
                    actual_date=teaching_session.actual_date,
                    effective_date=effective_date,
                    billable=billable,
                    billing_contribution=unit_fee if billable else Decimal("0"),
                    explanation=explanation,
                )
            )
        return tuple(rows)

    @classmethod
    def _payment_rows(cls, payments) -> Tuple[TuitionPaymentDetail, ...]:
        return tuple(
            TuitionPaymentDetail(
                income_id=int(payment.id),
                payment_date=payment.payment_date,
                amount=cls._amount(payment.amount),
                wallet=payment.payment_method,
                payment_period=payment.payment_period,
                finance_period_start=payment.finance_period_start,
                received_by=payment.received_by,
                note=payment.note,
            )
            for payment in sorted(payments, key=lambda item: (item.payment_date, item.id or 0))
        )

    def get_detail(
        self,
        enrollment_id: int,
        *,
        as_of_date: Optional[date] = None,
    ) -> TuitionDetailReadModel:
        cutoff = as_of_date or get_clock().today()
        with self._session_factory() as db_session:
            enrollment = self._repository_provider.enrollments(db_session).get_by_id(
                enrollment_id
            )
            if enrollment is None or enrollment.class_id is None:
                raise TuitionDetailNotFoundError(
                    f"Enrollment #{enrollment_id} was not found or has no class."
                )

            class_obj = enrollment.class_ or self._repository_provider.classes(
                db_session
            ).get_by_id(enrollment.class_id)
            student = enrollment.student or self._repository_provider.students(
                db_session
            ).get_by_id(enrollment.student_id)
            if class_obj is None or student is None:
                raise TuitionDetailNotFoundError(
                    f"Enrollment #{enrollment_id} references missing student/class data."
                )

            sessions = self._repository_provider.sessions(db_session).get_by_class(
                enrollment.class_id
            )
            income_repo = self._repository_provider.incomes(db_session)
            payments = income_repo.list_records(
                enrollment_id=enrollment_id,
                income_type=self.TUITION_INCOME_TYPE,
                date_to=cutoff,
                status=Income.STATUS_ACTIVE,
                offset=0,
                limit=100000,
                sort_by="payment_date",
                ascending=True,
            )
            paid = self._amount(
                income_repo.sum_active_tuition_for_enrollment(
                    enrollment_id,
                    as_of_date=cutoff,
                )
            )

            configured = enrollment.has_tuition_contract
            billable_numbers = ()
            gross = Decimal("0")
            recognized_discount = Decimal("0")
            net = Decimal("0")
            if configured:
                try:
                    accrual = TuitionAccrualService.calculate_from_records(
                        enrollment,
                        sessions,
                        cutoff,
                    )
                except TuitionAccrualUnresolvedError:
                    configured = False
                else:
                    billable_numbers = accrual.billable_session_numbers
                    gross = self._amount(accrual.gross_accrued)
                    recognized_discount = self._amount(accrual.discount)
                    net = self._amount(accrual.net_accrued)

            unit_fee = self._amount(enrollment.unit_fee) if enrollment.unit_fee is not None else Decimal("0")
            session_rows = self._session_rows(
                enrollment,
                sessions,
                as_of_date=cutoff,
                billable_numbers=billable_numbers,
                unit_fee=unit_fee,
            )
            completed_sessions = sum(
                1
                for row in session_rows
                if row.effective_date <= cutoff
                and row.status == SessionStatus.COMPLETED.value
            )

            balance_projection = OutstandingDTO.create(
                student_id=enrollment.student_id,
                student_name=student.full_name,
                student_code=student.student_code,
                class_id=enrollment.class_id,
                class_name=class_obj.name,
                expected_tuition=net,
                paid=paid,
                tuition_configured=configured,
                course_name=enrollment.course_name or class_obj.course,
                enrollment_id=int(enrollment.id),
            )

            return TuitionDetailReadModel(
                enrollment_id=int(enrollment.id),
                student_id=enrollment.student_id,
                student_name=student.full_name,
                student_code=student.student_code,
                class_id=enrollment.class_id,
                class_name=class_obj.name,
                course_name=enrollment.course_name or class_obj.course,
                as_of_date=cutoff,
                tuition_configured=configured,
                agreed_course_fee=(
                    self._amount(enrollment.agreed_course_fee)
                    if enrollment.agreed_course_fee is not None
                    else None
                ),
                planned_sessions=enrollment.planned_sessions,
                enrolled_from_session=enrollment.enrolled_from_session,
                enrolled_until_session=enrollment.enrolled_until_session,
                unit_fee=(unit_fee if enrollment.unit_fee is not None else None),
                contract_discount=self._amount(enrollment.discount_amount),
                completed_sessions=completed_sessions,
                billable_sessions=len(billable_numbers),
                gross_accrued=gross,
                recognized_discount=recognized_discount,
                net_accrued=net,
                paid=paid,
                balance=self._amount(balance_projection.outstanding),
                balance_state=balance_projection.balance_state,
                status=balance_projection.status,
                debt_amount=self._amount(balance_projection.debt_amount),
                prepaid_amount=self._amount(balance_projection.prepaid_amount),
                sessions=session_rows,
                payments=self._payment_rows(payments),
            )
