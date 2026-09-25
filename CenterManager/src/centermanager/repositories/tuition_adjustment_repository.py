# -*- coding: utf-8 -*-
"""Persistence boundary for tuition adjustment ledger rows."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.base import BaseRepository


class TuitionAdjustmentRepository(BaseRepository[TuitionAdjustment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TuitionAdjustment)

    def add(self, adjustment: TuitionAdjustment) -> TuitionAdjustment:
        self._session.add(adjustment)
        return adjustment

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, adjustment: TuitionAdjustment) -> TuitionAdjustment:
        self._session.refresh(adjustment)
        return adjustment

    def get_by_id(self, adjustment_id: int) -> Optional[TuitionAdjustment]:
        return self._session.query(TuitionAdjustment).filter(
            TuitionAdjustment.id == adjustment_id
        ).first()

    def get_by_idempotency_key(self, key: str) -> Optional[TuitionAdjustment]:
        return self._session.query(TuitionAdjustment).filter(
            TuitionAdjustment.idempotency_key == key
        ).first()

    def lock_origin_income(self, income_id: int):
        from centermanager.models.income import Income

        return self._session.query(Income).filter(Income.id == income_id).with_for_update().first()

    def lock_enrollment(self, enrollment_id: int):
        from centermanager.models.enrollment import Enrollment

        return self._session.query(Enrollment).filter(Enrollment.id == enrollment_id).with_for_update().first()

    def sum_refunds_for_origin(self, origin_income_id: int) -> Decimal:
        value = self._session.query(func.coalesce(func.sum(TuitionAdjustment.amount), 0)).filter(
            TuitionAdjustment.kind == TuitionAdjustment.KIND_REFUND,
            TuitionAdjustment.origin_income_id == origin_income_id,
        ).scalar()
        return Decimal(str(value or 0))

    def sum_credit_for_enrollment(
        self, enrollment_id: int, *, as_of_date: Optional[date] = None
    ) -> Decimal:
        query = self._session.query(func.coalesce(func.sum(TuitionAdjustment.amount), 0)).filter(
            TuitionAdjustment.kind == TuitionAdjustment.KIND_CREDIT,
            TuitionAdjustment.enrollment_id == enrollment_id,
        )
        if as_of_date is not None:
            query = query.filter(TuitionAdjustment.adjustment_date <= as_of_date)
        return Decimal(str(query.scalar() or 0))
