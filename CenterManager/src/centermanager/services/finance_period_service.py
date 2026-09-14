from __future__ import annotations

from datetime import date
from typing import List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from centermanager.core.current_user import get_current_user
from centermanager.core.permission_guard import require_permission
from centermanager.models.finance_period import FinancePeriod, FinancePeriodDefinition
from centermanager.repositories.provider import RepositoryProvider, create_default_repository_provider


class FinancePeriodService:
    """Admin-managed configuration and pure period calculations for Finance."""

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or create_default_repository_provider()

    @require_permission("finance.period.view")
    def get_active_period(self, on_date: Optional[date] = None) -> Optional[FinancePeriod]:
        target = on_date or date.today()
        with self._session_factory() as session:
            return self._repository_provider.finance_periods(session).get_active(target)

    @require_permission("finance.period.view")
    def list_period_configurations(self) -> List[FinancePeriod]:
        with self._session_factory() as session:
            return self._repository_provider.finance_periods(session).list_all()

    @require_permission("finance.period.manage")
    def configure(
        self,
        duration_months: int,
        effective_from: date,
    ) -> FinancePeriod:
        FinancePeriod.validate_duration(duration_months)
        if effective_from is None:
            raise ValueError("effective_from is required.")

        current_user = get_current_user()
        if current_user is None or not getattr(current_user, "is_admin", False):
            raise PermissionError("Only administrators can configure finance periods.")

        with self._session_factory() as session:
            repo = self._repository_provider.finance_periods(session)
            if repo.exists_effective_from(effective_from):
                raise ValueError("A finance period configuration already exists for this effective date.")

            previous = repo.get_active(effective_from)
            period = FinancePeriod(
                duration_months=duration_months,
                status=FinancePeriod.STATUS_ACTIVE,
                effective_from=effective_from,
                effective_to=None,
            )
            if previous is not None and previous.effective_from < effective_from:
                previous.effective_to = effective_from.fromordinal(effective_from.toordinal() - 1)
                previous.status = FinancePeriod.STATUS_INACTIVE

            repo.add(period)
            session.commit()
            repo.refresh(period)
            return period

    @require_permission("finance.period.manage")
    def deactivate(self, period_id: int, effective_to: Optional[date] = None) -> FinancePeriod:
        current_user = get_current_user()
        if current_user is None or not getattr(current_user, "is_admin", False):
            raise PermissionError("Only administrators can configure finance periods.")

        with self._session_factory() as session:
            repo = self._repository_provider.finance_periods(session)
            period = repo.get_by_id(period_id)
            if period is None:
                raise ValueError(f"Finance period {period_id} not found.")
            period.status = FinancePeriod.STATUS_INACTIVE
            period.effective_to = effective_to or date.today()
            session.commit()
            repo.refresh(period)
            return period

    @staticmethod
    def get_period_bounds(anchor_date: date, target_date: date, duration_months: int) -> Tuple[date, date]:
        return FinancePeriodDefinition.period_for_date(anchor_date, target_date, duration_months)

    @staticmethod
    def get_period_index(anchor_date: date, target_date: date, duration_months: int) -> int:
        FinancePeriod.validate_duration(duration_months)
        if target_date >= anchor_date:
            months = (target_date.year - anchor_date.year) * 12 + target_date.month - anchor_date.month
            if target_date.day < anchor_date.day:
                months -= 1
        else:
            months = -((anchor_date.year - target_date.year) * 12 + anchor_date.month - target_date.month)
            if target_date.day > anchor_date.day:
                months += 1
        return months // duration_months
