from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class EmployeeWorkRegistrationPeriod(Base, TimestampMixin):
    """Weekly container controlling the lifecycle of employee availability registration."""
    __tablename__ = "employee_work_registration_periods"

    STATUS_OPEN = "OPEN"
    STATUS_CLOSED = "CLOSED"
    VALID_STATUSES = {STATUS_OPEN, STATUS_CLOSED}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_OPEN, server_default=STATUS_OPEN)
    submission_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    registrations: Mapped[List["EmployeeWorkRegistration"]] = relationship(
        "EmployeeWorkRegistration", back_populates="period", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("week_start", name="uq_employee_work_registration_period_week"),
    )

    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=6)

    @property
    def key(self) -> date:
        return self.week_start
