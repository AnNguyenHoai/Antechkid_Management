from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod


class EmployeeWorkRegistrationPeriodRepository:
    """Persistence adapter for employee work-registration periods."""

    def __init__(self, session: Session):
        self._session = session

    def get_by_year_month(self, year: int, month: int) -> Optional[EmployeeWorkRegistrationPeriod]:
        return self._session.scalar(
            select(EmployeeWorkRegistrationPeriod).where(
                EmployeeWorkRegistrationPeriod.year == year,
                EmployeeWorkRegistrationPeriod.month == month,
            )
        )

    def get_or_create(self, year: int, month: int) -> EmployeeWorkRegistrationPeriod:
        period = self.get_by_year_month(year, month)
        if period is None:
            period = EmployeeWorkRegistrationPeriod(year=year, month=month)
            self._session.add(period)
            self._session.flush()
        return period
