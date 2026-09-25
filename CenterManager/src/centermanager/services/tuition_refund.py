# -*- coding: utf-8 -*-
"""Compatibility adapter for the TUITION-14 refund API."""
from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from centermanager.events.event_bus import EventBus
from centermanager.models.income import Income
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider
from centermanager.services.audit_service import AuditService
from centermanager.services.tuition_adjustment_service import (
    TuitionAdjustmentService,
    TuitionAdjustmentValidationError,
    _money,
)


class TuitionRefundError(Exception):
    pass


class TuitionRefundValidationError(TuitionRefundError):
    pass


class TuitionRefundService:
    """Preserve the old API while enforcing the first-class adjustment ledger."""

    REFUND_TYPE = "Tuition"
    REFUND_MARKER = "tuition_adjustment_refund"
    ORIGIN_MARKER = "origin_income_id="

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
        audit_service: Optional[AuditService] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()
        self._adjustments = TuitionAdjustmentService(
            session_factory,
            repository_provider=self._repository_provider,
            audit_service=audit_service,
            event_bus=event_bus,
        )

    @staticmethod
    def _reason(value: str) -> str:
        reason = (value or "").strip()
        if not reason:
            raise TuitionRefundValidationError("Refund reason is required.")
        return reason

    def preview(self, enrollment_id: int, *, as_of_date: Optional[date] = None) -> dict:
        try:
            return self._adjustments.preview(enrollment_id, as_of_date=as_of_date)
        except TuitionAdjustmentValidationError as exc:
            raise TuitionRefundValidationError(str(exc)) from exc

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
        idempotency_key: Optional[str] = None,
    ) -> Income:
        resolved_reason = self._reason(reason)
        key = idempotency_key or f"legacy-refund-{uuid4()}"
        try:
            adjustment = self._adjustments.refund(
                enrollment_id,
                amount,
                payment_method,
                refund_date,
                reason=resolved_reason,
                idempotency_key=key,
                origin_income_id=origin_income_id,
                prepaid_only=prepaid_only,
            )
        except TuitionAdjustmentValidationError as exc:
            raise TuitionRefundValidationError(str(exc)) from exc
        with self._session_factory() as session:
            income = self._repository_provider.incomes(session).get_by_id(
                adjustment.linked_income_id
            )
            if income is None:
                raise TuitionRefundValidationError(
                    "Refund adjustment is missing its linked Income row."
                )
            return income
