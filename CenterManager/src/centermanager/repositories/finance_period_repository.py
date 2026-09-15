from __future__ import annotations

from datetime import date
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from centermanager.models.finance_period import FinancePeriod


class FinancePeriodRepository:
    """Persistence adapter for finance-period configurations."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, period: FinancePeriod) -> FinancePeriod:
        self._session.add(period)
        return period

    def refresh(self, period: FinancePeriod) -> FinancePeriod:
        self._session.refresh(period)
        return period

    def get_by_id(self, period_id: int) -> Optional[FinancePeriod]:
        return self._session.scalar(
            select(FinancePeriod).where(FinancePeriod.id == period_id)
        )

    def get_active(self, on_date: date) -> Optional[FinancePeriod]:
        return self._session.scalar(
            select(FinancePeriod)
            .where(
                FinancePeriod.status == FinancePeriod.STATUS_ACTIVE,
                FinancePeriod.effective_from <= on_date,
                (FinancePeriod.effective_to.is_(None) | (FinancePeriod.effective_to >= on_date)),
            )
            .order_by(FinancePeriod.effective_from.desc())
        )

    def list_all(self) -> List[FinancePeriod]:
        return list(
            self._session.scalars(
                select(FinancePeriod).order_by(FinancePeriod.effective_from.desc())
            ).all()
        )

    def exists_effective_from(self, effective_from: date) -> bool:
        return self._session.scalar(
            select(FinancePeriod.id).where(FinancePeriod.effective_from == effective_from)
        ) is not None
