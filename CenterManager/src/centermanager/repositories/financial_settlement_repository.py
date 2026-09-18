from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from centermanager.models.financial_settlement import FinancialSettlement
from centermanager.repositories.base import BaseRepository


class FinancialSettlementRepository(BaseRepository[FinancialSettlement]):
    """Persistence adapter for FinancePeriod settlement snapshots."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, FinancialSettlement)

    def get_by_period_start(self, period_start: date) -> Optional[FinancialSettlement]:
        return self._session.scalar(
            select(FinancialSettlement).where(
                FinancialSettlement.finance_period_start == period_start
            )
        )
