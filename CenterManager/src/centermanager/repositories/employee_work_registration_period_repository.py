from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod


class EmployeeWorkRegistrationPeriodRepository:
    """Persistence adapter for weekly employee work-registration periods."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def normalize_week_start(value: date) -> date:
        if not isinstance(value, date):
            raise ValueError("week_start must be a date")
        return value - timedelta(days=value.weekday())

    def get_by_week_start(self, week_start: date) -> Optional[EmployeeWorkRegistrationPeriod]:
        week_start = self.normalize_week_start(week_start)
        return self._session.scalar(
            select(EmployeeWorkRegistrationPeriod).where(
                EmployeeWorkRegistrationPeriod.week_start == week_start
            )
        )

    def get_or_create(self, week_start: date) -> EmployeeWorkRegistrationPeriod:
        week_start = self.normalize_week_start(week_start)
        period = self.get_by_week_start(week_start)
        if period is None:
            period = EmployeeWorkRegistrationPeriod(week_start=week_start)
            self._session.add(period)
            self._session.flush()
        return period

    def refresh(self, period: EmployeeWorkRegistrationPeriod) -> None:
        self._session.refresh(period)

    def detach(self, period: EmployeeWorkRegistrationPeriod) -> None:
        self._session.expunge(period)
