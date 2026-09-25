# -*- coding: utf-8 -*-
"""First-class tuition refund and non-cash credit adjustment workflow."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.core.wallet import WalletMappingError, canonical_wallet_value
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.models.income import Income
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.audit_service import AuditService
from centermanager.services.finance_ledger_guard import FinanceLedgerGuard


_MONEY_QUANTUM = Decimal("0.01")


class TuitionAdjustmentError(Exception):
    pass


class TuitionAdjustmentValidationError(TuitionAdjustmentError):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)


class TuitionAdjustmentService:
    """Create immutable adjustments with repository-owned persistence and locking."""

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._audit_service = audit_service or AuditService(
            session_factory, repository_provider=self._repository_provider
        )
        self._event_bus = event_bus

    @staticmethod
    def _reason(value: str) -> str:
        reason = (value or "").strip()
        if not reason:
            raise TuitionAdjustmentValidationError("Adjustment reason is required.")
        return reason

    @staticmethod
    def _idempotency_key(value: str) -> str:
        key = (value or "").strip()
        if not key:
            raise TuitionAdjustmentValidationError("Idempotency key is required.")
        if len(key) > 120:
            raise TuitionAdjustmentValidationError("Idempotency key is too long.")
        return key

    @staticmethod
    def _wallet(value: str) -> str:
        try:
            return canonical_wallet_value(value)
        except WalletMappingError as exc:
            raise TuitionAdjustmentValidationError(str(exc)) from exc

    @staticmethod
    def _actor_name(actor) -> str:
        return (
            getattr(actor, "full_name", None)
            or getattr(actor, "username", None)
            or "System"
        )

    def _publish(self, adjustment: TuitionAdjustment) -> None:
        if self._event_bus is None:
            return
        self._event_bus.publish(
            FinanceDataChanged(
                entity="tuition_adjustment",
                action=adjustment.kind.lower(),
                entity_id=adjustment.id,
            )
        )
        if adjustment.linked_income_id is not None:
            self._event_bus.publish(
                FinanceDataChanged(
                    entity="income",
                    action="created",
                    entity_id=adjustment.linked_income_id,
                )
            )

    def _ensure_date_mutable(self, session, adjustment_date: date):
        try:
            resolved = FinanceLedgerGuard.ensure_date_mutable(
                session, self._repository_provider, adjustment_date
            )
            config = self._repository_provider.finance_periods(
                session
            ).get_unique_effective(adjustment_date)
        except ValueError as exc:
            raise TuitionAdjustmentValidationError(str(exc)) from exc
        if config is None:
            raise TuitionAdjustmentValidationError(
                f"No accounting configuration covers adjustment date {adjustment_date.isoformat()}."
            )
        return config, resolved.period_start

    @staticmethod
    def _validate_date(value: date) -> date:
        if value is None:
            raise TuitionAdjustmentValidationError("Adjustment date is required.")
        if value > get_clock().today():
            raise TuitionAdjustmentValidationError("Adjustment date cannot be in the future.")
        return value

    @staticmethod
    def _validate_amount(value) -> Decimal:
        amount = _money(value)
        if amount <= 0:
            raise TuitionAdjustmentValidationError("Adjustment amount must be greater than 0.")
        return amount

    @staticmethod
    def _same_command(
        existing: TuitionAdjustment,
        *,
        kind: str,
        enrollment_id: int,
        amount: Decimal,
        adjustment_date: date,
        origin_income_id: Optional[int],
        wallet: Optional[str],
        reason: str,
    ) -> bool:
        return (
            existing.kind == kind
            and existing.enrollment_id == enrollment_id
            and _money(existing.amount) == amount
            and existing.adjustment_date == adjustment_date
            and existing.origin_income_id == origin_income_id
            and existing.wallet == wallet
            and existing.reason == reason
        )

    def _return_existing_or_conflict(self, repo, key: str, **command) -> Optional[TuitionAdjustment]:
        existing = repo.get_by_idempotency_key(key)
        if existing is None:
            return None
        if not self._same_command(existing, **command):
            raise TuitionAdjustmentValidationError(
                "Idempotency key is already used by a different adjustment command."
            )
        return existing

    def preview(
        self,
        enrollment_id: int,
        *,
        origin_income_id: Optional[int] = None,
        as_of_date: Optional[date] = None,
    ) -> dict:
        cutoff = as_of_date or get_clock().today()
        with self._session_factory() as session:
            enrollment = self._repository_provider.enrollments(session).get_by_id(enrollment_id)
            if enrollment is None:
                raise TuitionAdjustmentValidationError("Enrollment not found.")
            incomes = self._repository_provider.incomes(session)
            adjustments = self._repository_provider.tuition_adjustments(session)
            settled = _money(
                incomes.sum_active_tuition_for_enrollment(enrollment_id, as_of_date=cutoff)
            )
            result = {
                "enrollment_id": enrollment_id,
                "refundable_amount": max(settled, Decimal("0.00")),
                "as_of_date": cutoff,
            }
            if origin_income_id is not None:
                origin = incomes.get_by_id(origin_income_id)
                if (
                    origin is None
                    or origin.income_type != "Tuition"
                    or origin.status != Income.STATUS_ACTIVE
                    or float(origin.amount) <= 0
                    or origin.enrollment_id != enrollment_id
                ):
                    raise TuitionAdjustmentValidationError(
                        "Origin must be a positive ACTIVE Tuition payment for this Enrollment."
                    )
                refunded = _money(adjustments.sum_refunds_for_origin(origin_income_id))
                result["origin_remaining_refundable"] = max(
                    _money(origin.amount) - refunded, Decimal("0.00")
                )
            return result

    @require_permission("finance.income.create")
    def refund(
        self,
        enrollment_id: int,
        amount,
        payment_method: str,
        adjustment_date: date,
        *,
        reason: str,
        idempotency_key: str,
        origin_income_id: Optional[int] = None,
        prepaid_only: bool = False,
    ) -> TuitionAdjustment:
        value = self._validate_amount(amount)
        effective_date = self._validate_date(adjustment_date)
        resolved_reason = self._reason(reason)
        key = self._idempotency_key(idempotency_key)
        wallet = self._wallet(payment_method)
        command = dict(
            kind=TuitionAdjustment.KIND_REFUND,
            enrollment_id=enrollment_id,
            amount=value,
            adjustment_date=effective_date,
            origin_income_id=origin_income_id,
            wallet=wallet,
            reason=resolved_reason,
        )

        try:
            with self._session_factory() as session:
                adjustments = self._repository_provider.tuition_adjustments(session)
                existing = self._return_existing_or_conflict(adjustments, key, **command)
                if existing is not None:
                    return existing

                enrollment = adjustments.lock_enrollment(enrollment_id)
                if enrollment is None:
                    raise TuitionAdjustmentValidationError("Enrollment not found.")
                incomes = self._repository_provider.incomes(session)

                if origin_income_id is not None:
                    origin = adjustments.lock_origin_income(origin_income_id)
                    if (
                        origin is None
                        or origin.deleted_at is not None
                        or origin.income_type != "Tuition"
                        or origin.status != Income.STATUS_ACTIVE
                        or float(origin.amount) <= 0
                    ):
                        raise TuitionAdjustmentValidationError(
                            "Origin must be an ACTIVE positive Tuition payment."
                        )
                    if origin.enrollment_id != enrollment_id:
                        raise TuitionAdjustmentValidationError(
                            "Origin payment belongs to a different Enrollment."
                        )
                    already_refunded = _money(
                        adjustments.sum_refunds_for_origin(origin_income_id)
                    )
                    remaining = max(
                        _money(origin.amount) - already_refunded, Decimal("0.00")
                    )
                    if value > remaining:
                        raise TuitionAdjustmentValidationError(
                            f"Refund amount {value} exceeds origin remaining refundable {remaining}."
                        )

                settled = _money(
                    incomes.sum_active_tuition_for_enrollment(
                        enrollment_id, as_of_date=effective_date
                    )
                )
                refundable = max(settled, Decimal("0.00"))
                if value > refundable:
                    raise TuitionAdjustmentValidationError(
                        f"Refund amount {value} exceeds refundable tuition {refundable}."
                    )

                if prepaid_only:
                    from centermanager.services.tuition_accrual_service import (
                        TuitionAccrualService,
                        TuitionAccrualUnresolvedError,
                    )

                    sessions = self._repository_provider.sessions(session).get_by_class(
                        enrollment.class_id
                    )
                    try:
                        accrual = TuitionAccrualService.calculate_from_records(
                            enrollment, sessions, effective_date
                        )
                    except TuitionAccrualUnresolvedError as exc:
                        raise TuitionAdjustmentValidationError(
                            "Enrollment tuition accrual is unresolved."
                        ) from exc
                    prepaid = max(
                        _money(settled - Decimal(accrual.net_accrued)), Decimal("0.00")
                    )
                    if value > prepaid:
                        raise TuitionAdjustmentValidationError(
                            f"Prepaid refund {value} exceeds available prepaid credit {prepaid}."
                        )

                accounting_config, accounting_period_start = self._ensure_date_mutable(
                    session, effective_date
                )
                actor = get_current_user()
                income = Income(
                    student_id=enrollment.student_id,
                    class_id=enrollment.class_id,
                    enrollment_id=enrollment.id,
                    amount=-float(value),
                    income_type="Tuition",
                    payment_method=wallet,
                    payment_date=effective_date,
                    payment_period="REFUND",
                    finance_period_id=accounting_config.id,
                    finance_period_start=accounting_period_start,
                    received_by=self._actor_name(actor),
                    note=f"tuition_adjustment_refund; reason={resolved_reason}",
                    status=Income.STATUS_ACTIVE,
                )
                incomes.add(income)
                incomes.flush()
                adjustment = TuitionAdjustment(
                    enrollment_id=enrollment.id,
                    origin_income_id=origin_income_id,
                    linked_income_id=income.id,
                    kind=TuitionAdjustment.KIND_REFUND,
                    amount=value,
                    adjustment_date=effective_date,
                    wallet=wallet,
                    reason=resolved_reason,
                    idempotency_key=key,
                    created_by=getattr(actor, "username", None),
                )
                adjustments.add(adjustment)
                adjustments.flush()
                self._audit_service.record_in_session(
                    session,
                    action="TUITION_REFUND",
                    module="tuition",
                    target_type="tuition_adjustment",
                    target_id=adjustment.id,
                    target_name=f"Tuition Refund #{adjustment.id}",
                    actor=actor,
                    details={
                        "enrollment_id": enrollment.id,
                        "origin_income_id": origin_income_id,
                        "linked_income_id": income.id,
                        "amount": str(value),
                        "wallet": wallet,
                        "adjustment_date": effective_date.isoformat(),
                        "accounting_period_start": accounting_period_start.isoformat(),
                        "prepaid_only": prepaid_only,
                        "idempotency_key": key,
                        "reason": resolved_reason,
                    },
                    entity_type="TuitionAdjustment",
                    entity_id=adjustment.id,
                    summary=f"Tuition refund for Enrollment#{enrollment.id}",
                )
                session.commit()
                adjustments.refresh(adjustment)
        except IntegrityError as exc:
            with self._session_factory() as replay_session:
                replay_repo = self._repository_provider.tuition_adjustments(replay_session)
                existing = self._return_existing_or_conflict(replay_repo, key, **command)
                if existing is not None:
                    return existing
            raise TuitionAdjustmentValidationError(
                "Concurrent adjustment conflicted with the current command; retry with the same idempotency key."
            ) from exc

        self._publish(adjustment)
        return adjustment

    @require_permission("finance.income.create")
    def credit_adjustment(
        self,
        enrollment_id: int,
        amount,
        adjustment_date: date,
        *,
        reason: str,
        idempotency_key: str,
        origin_adjustment_id: Optional[int] = None,
    ) -> TuitionAdjustment:
        value = self._validate_amount(amount)
        effective_date = self._validate_date(adjustment_date)
        resolved_reason = self._reason(reason)
        key = self._idempotency_key(idempotency_key)
        command = dict(
            kind=TuitionAdjustment.KIND_CREDIT,
            enrollment_id=enrollment_id,
            amount=value,
            adjustment_date=effective_date,
            origin_income_id=None,
            wallet=None,
            reason=resolved_reason,
        )

        try:
            with self._session_factory() as session:
                adjustments = self._repository_provider.tuition_adjustments(session)
                existing = self._return_existing_or_conflict(adjustments, key, **command)
                if existing is not None:
                    return existing
                enrollment = adjustments.lock_enrollment(enrollment_id)
                if enrollment is None:
                    raise TuitionAdjustmentValidationError("Enrollment not found.")
                if origin_adjustment_id is not None:
                    origin_adjustment = adjustments.get_by_id(origin_adjustment_id)
                    if origin_adjustment is None or origin_adjustment.enrollment_id != enrollment_id:
                        raise TuitionAdjustmentValidationError(
                            "Origin adjustment must belong to the same Enrollment."
                        )
                _, accounting_period_start = self._ensure_date_mutable(session, effective_date)
                actor = get_current_user()
                adjustment = TuitionAdjustment(
                    enrollment_id=enrollment.id,
                    origin_adjustment_id=origin_adjustment_id,
                    linked_income_id=None,
                    kind=TuitionAdjustment.KIND_CREDIT,
                    amount=value,
                    adjustment_date=effective_date,
                    wallet=None,
                    reason=resolved_reason,
                    idempotency_key=key,
                    created_by=getattr(actor, "username", None),
                )
                adjustments.add(adjustment)
                adjustments.flush()
                self._audit_service.record_in_session(
                    session,
                    action="TUITION_CREDIT_ADJUSTMENT",
                    module="tuition",
                    target_type="tuition_adjustment",
                    target_id=adjustment.id,
                    target_name=f"Tuition Credit Adjustment #{adjustment.id}",
                    actor=actor,
                    details={
                        "enrollment_id": enrollment.id,
                        "origin_adjustment_id": origin_adjustment_id,
                        "amount": str(value),
                        "adjustment_date": effective_date.isoformat(),
                        "accounting_period_start": accounting_period_start.isoformat(),
                        "idempotency_key": key,
                        "reason": resolved_reason,
                        "wallet_movement": False,
                    },
                    entity_type="TuitionAdjustment",
                    entity_id=adjustment.id,
                    summary=f"Tuition credit adjustment for Enrollment#{enrollment.id}",
                )
                session.commit()
                adjustments.refresh(adjustment)
        except IntegrityError as exc:
            with self._session_factory() as replay_session:
                replay_repo = self._repository_provider.tuition_adjustments(replay_session)
                existing = self._return_existing_or_conflict(replay_repo, key, **command)
                if existing is not None:
                    return existing
            raise TuitionAdjustmentValidationError(
                "Concurrent adjustment conflicted with the current command; retry with the same idempotency key."
            ) from exc

        self._publish(adjustment)
        return adjustment
