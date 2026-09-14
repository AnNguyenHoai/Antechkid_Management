from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Optional, Tuple

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class FinancePeriod(Base, TimestampMixin):
    """Canonical finance period configuration.

    One active configuration defines the duration, in calendar months, used by
    Finance to partition time into billing/reporting periods. The configured
    duration is intentionally stored as domain data rather than hard-coded in
    Finance services.
    """

    __tablename__ = "finance_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", server_default="ACTIVE")
    effective_from: Mapped[date] = mapped_column(nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(nullable=True)

    __table_args__ = (
        UniqueConstraint("effective_from", name="uq_finance_period_effective_from"),
    )

    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    VALID_STATUSES = frozenset({STATUS_ACTIVE, STATUS_INACTIVE})

    MIN_DURATION_MONTHS = 1
    MAX_DURATION_MONTHS = 24

    def __post_init__(self) -> None:
        self.validate_duration(self.duration_months)
        self.validate_status(self.status)

    @classmethod
    def validate_duration(cls, duration_months: int) -> int:
        if isinstance(duration_months, bool) or not isinstance(duration_months, int):
            raise ValueError("duration_months must be an integer.")
        if not cls.MIN_DURATION_MONTHS <= duration_months <= cls.MAX_DURATION_MONTHS:
            raise ValueError(
                f"duration_months must be between {cls.MIN_DURATION_MONTHS} "
                f"and {cls.MAX_DURATION_MONTHS}."
            )
        return duration_months

    @classmethod
    def validate_status(cls, status: str) -> str:
        if status not in cls.VALID_STATUSES:
            raise ValueError(f"Invalid FinancePeriod status: {status}")
        return status

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    def contains(self, target_date: date) -> bool:
        """Return whether target_date lies inside this configured period."""
        if target_date < self.effective_from:
            return False
        if self.effective_to is not None and target_date > self.effective_to:
            return False
        return True

    def key(self) -> Tuple[int, int]:
        return self.duration_months, self.effective_from.toordinal()

    def __repr__(self) -> str:
        return (
            f"<FinancePeriod(id={self.id}, duration_months={self.duration_months}, "
            f"effective_from={self.effective_from}, status={self.status})>"
        )


class FinancePeriodDefinition:
    """Pure domain helper for calculating period boundaries."""

    @staticmethod
    def add_months(source_date: date, months: int) -> date:
        FinancePeriod.validate_duration(months)
        absolute = source_date.year * 12 + (source_date.month - 1) + months
        year, month_index = divmod(absolute, 12)
        month = month_index + 1
        day = min(source_date.day, monthrange(year, month)[1])
        return date(year, month, day)

    @classmethod
    def bounds_for(cls, start_date: date, duration_months: int) -> tuple[date, date]:
        end_exclusive = cls.add_months(start_date, duration_months)
        return start_date, end_exclusive.fromordinal(end_exclusive.toordinal() - 1)

    @classmethod
    def period_for_date(
        cls, anchor_date: date, target_date: date, duration_months: int
    ) -> tuple[date, date]:
        FinancePeriod.validate_duration(duration_months)
        if target_date >= anchor_date:
            months = (
                (target_date.year - anchor_date.year) * 12
                + target_date.month
                - anchor_date.month
            )
        else:
            months = -(
                (anchor_date.year - target_date.year) * 12
                + anchor_date.month
                - target_date.month
            )

        bucket = months // duration_months
        candidate = cls.add_months(anchor_date, bucket * duration_months)
        if candidate > target_date:
            candidate = cls.add_months(candidate, -duration_months)
        return cls.bounds_for(candidate, duration_months)
