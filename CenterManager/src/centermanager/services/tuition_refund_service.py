# -*- coding: utf-8 -*-
"""TUITION-14 explicit, auditable tuition refund workflow.

Refunds are immutable adjustment transactions. They never edit or void the
originating Tuition payment. A refund is represented as a negative ACTIVE
Income row with ``income_type='Tuition Refund'`` so Wallet/Settlement sees the
real cash outflow in the refund's own Finance period while tuition settlement
for the Enrollment is reduced by the same amount.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.core.wallet import WalletMappingError, canonical_wallet_value
from centermanager.models.finance_period import FinancePeriodDefinition
from centermanager.models.income import Income
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.audit_service import AuditService
from centermanager.services.finance_ledger_guard import FinanceLedgerGuard, FinancePeriodClosedError


_MONEY_QUANTUM = Decimal("0.01")


class TuitionRefundError(Exception):
    pass


class TuitionRefundValidationError(TuitionRefundError):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class TuitionRefundService:
    """Post refund adjustments without rewriting Tuition payment history."""

    REFUND_TYPE = "Tuition Refund"
    ORIGIN_MARKER = "origin_income_id="

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=self._repository_provider
        )

    @staticmethod
    def _reason(value: str) -> str:
        reason = (value or "").strip()
        if not reason:
            raise TuitionRefundValidationError("Refund reason is required.")
        return reason

    @staticmethod
    def _wallet(value: str) -> str:
        try:
            return canonical_wallet_value(value)
        except WalletMappingError as exc:
            raise TuitionRefundValidationError(str(exc)) from exc

    def _resolve_period(self, session, refund_date: date):
        try:
            config = self._repository_provider.finance_periods(session).get_unique_effective(refund_date)
        except ValueError as exc:
            raise TuitionRefundValidationError(str(exc)) from exc
        if config is None:
            raise TuitionRefundValidationError(
                f"No Finance period configuration covers refund date {refund_date.isoformat()}."
            )
        resolved = FinancePeriodDefinition.resolved_for_configuration(config, refund_date)
        try:
            FinanceLedgerGuard.ensure_period_start_mutable(
                session, self._repository_provider, resolved.period_start
            )
        except FinancePeriodClosedError as exc:
            raise TuitionRefundValidationError(str(exc)) from exc
        return config, resolved.period_start

    def preview(self, enrollment_id: int, *, as_of_date: Optional[date] = None) -> dict:
        cutoff = as_of_date or get_clock().today()
        with self._session_factory() as session:
            enrollment = self._repository_provider.enrollments(session).get_by_id(enrollment_id)
            if enrollment is None:
                raise TuitionRefundValidationError("Enrollment not found.")
            settled = self._repository_provider.incomes(session).sum_active_tuition_for_enrollment(
                enrollment_id, as_of_date=cutoff
            )
            return {
                "enrollment_id": enrollment_id,
                "refundable_amount": max(_money(settled), Decimal("0.00")),
                "as_of_date": cutoff,
            }

    @require_permission("finance.income.create")
    def refund(
        self,
        enrollment_id: int,
        amount,
        payment_method: str,
        refund_date: date,
        *,
        reason: str,
        origin_income_id: Optional[int] = None,
        prepaid_only: bool = False,
    ) -> Income:
        value = _money(amount)
        if value <= 0:
            raise TuitionRefundValidationError("Refund amount must be greater than 0.")
        if refund_date is None:
            raise TuitionRefundValidationError("Refund date is required.")
        if refund_date > get_clock().today():
            raise TuitionRefundValidationError("Refund date cannot be in the future.")
        resolved_reason = self._reason(reason)
        wallet = self._wallet(payment_method)

        with self._session_factory() as session:
            enrollments = self._repository_provider.enrollments(session)
            incomes = self._repository_provider.incomes(session)
            enrollment = enrollments.get_by_id(enrollment_id)
            if enrollment is None:
                raise TuitionRefundValidationError("Enrollment not found.")

            origin = None
            if origin_income_id is not None:
                origin = incomes.get_by_id(origin_income_id)
                if origin is None or origin.income_type != "Tuition" or origin.status != Income.STATUS_ACTIVE:
                    raise TuitionRefundValidationError("Origin must be an ACTIVE Tuition payment.")
                if origin.enrollment_id != enrollment_id:
                    raise TuitionRefundValidationError("Origin payment belongs to a different Enrollment.")

            settled = _money(
                incomes.sum_active_tuition_for_enrollment(
                    enrollment_id, as_of_date=refund_date
                )
            )
            refundable = max(settled, Decimal("0.00"))
            if value > refundable:
                raise TuitionRefundValidationError(
                    f"Refund amount {value} exceeds refundable tuition {refundable}."
                )

            if prepaid_only:
                from centermanager.services.tuition_accrual_service import TuitionAccrualService, TuitionAccrualUnresolvedError

                sessions = self._repository_provider.sessions(session).get_by_class(enrollment.class_id)
                try:
                    accrual = TuitionAccrualService.calculate_from_records(
                        enrollment, sessions, refund_date
                    )
                except TuitionAccrualUnresolvedError as exc:
                    raise TuitionRefundValidationError("Enrollment tuition accrual is unresolved.") from exc
                prepaid = max(_money(settled - Decimal(accrual.net_accrued)), Decimal("0.00"))
                if value > prepaid:
                    raise TuitionRefundValidationError(
                        f"Prepaid refund {value} exceeds available prepaid credit {prepaid}."
                    )

            finance_period, finance_period_start = self._resolve_period(session, refund_date)
            origin_marker = (
                f"{self.ORIGIN_MARKER}{origin_income_id}; " if origin_income_id is not None else ""
            )
            note = f"{origin_marker}refund_reason={resolved_reason}"
            actor = get_current_user()
            actor_name = getattr(actor, "full_name", None) or getattr(actor, "username", None) or "System"
            adjustment = Income(
                student_id=enrollment.student_id,
                class_id=enrollment.class_id,
                enrollment_id=enrollment.id,
                amount=-float(value),
                income_type=self.REFUND_TYPE,
                payment_method=wallet,
                payment_date=refund_date,
                finance_period_id=finance_period.id,
                finance_period_start=finance_period_start,
                received_by=actor_name,
                note=note,
                status=Income.STATUS_ACTIVE,
            )
            incomes.add(adjustment)
            incomes.flush()
            self._audit_service.record_in_session(
                session,
                action="TUITION_REFUND",
                module="tuition",
                target_type="income",
                target_id=adjustment.id,
                target_name=f"Tuition Refund #{adjustment.id}",
                actor=actor,
                details={
                    "enrollment_id": enrollment.id,
                    "origin_income_id": origin_income_id,
                    "amount": str(value),
                    "payment_method": wallet,
                    "refund_date": refund_date.isoformat(),
                    "finance_period_start": finance_period_start.isoformat(),
                    "prepaid_only": prepaid_only,
                    "reason": resolved_reason,
                },
                entity_type="Income",
                entity_id=adjustment.id,
                summary=f"Tuition refund for Enrollment#{enrollment.id}",
            )
            session.commit()
            incomes.refresh(adjustment)
            return adjustment
