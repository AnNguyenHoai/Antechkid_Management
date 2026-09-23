from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy import CheckConstraint, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


@dataclass(frozen=True)
class ResolvedFinancePeriod:
    """Canonical operating-period bounds resolved from one FinancePeriod config.

    ``FinancePeriod`` remains configuration/lifecycle persistence. This value
    object represents the exact operating bucket consumed by Wallet/Settlement
    code and is deliberately not persisted as a second period table.
    """

    configuration_id: Optional[int]
    period_start: date
    period_end: date

    def contains(self, target_date: date) -> bool:
        return self.period_start <= target_date <= self.period_end


class FinancePeriod(Base, TimestampMixin):
    """Canonical finance-period configuration used by Finance features."""

    __tablename__ = "finance_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", server_default="ACTIVE")
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("effective_from", name="uq_finance_period_effective_from"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_finance_period_effective_range",
        ),
    )

    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    VALID_STATUSES = frozenset({STATUS_ACTIVE, STATUS_INACTIVE})
    MIN_DURATION_MONTHS = 1
    MAX_DURATION_MONTHS = 24

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
        if target_date < self.effective_from:
            return False
        return self.effective_to is None or target_date <= self.effective_to

    def __repr__(self) -> str:
        return (
            f"<FinancePeriod(id={self.id}, duration_months={self.duration_months}, "
            f"effective_from={self.effective_from}, status={self.status})>"
        )


class FinancePeriodDefinition:
    """Pure calculations for duration-based Finance operating periods."""

    @staticmethod
    def add_months(source_date: date, months: int) -> date:
        if not isinstance(months, int):
            raise ValueError("months must be an integer.")
        absolute = source_date.year * 12 + (source_date.month - 1) + months
        year, month_index = divmod(absolute, 12)
        month = month_index + 1
        day = min(source_date.day, monthrange(year, month)[1])
        return date(year, month, day)

    @classmethod
    def bounds_for(cls, start_date: date, duration_months: int) -> tuple[date, date]:
        FinancePeriod.validate_duration(duration_months)
        end_exclusive = cls.add_months(start_date, duration_months)
        return start_date, date.fromordinal(end_exclusive.toordinal() - 1)

    @classmethod
    def period_for_date(
        cls, anchor_date: date, target_date: date, duration_months: int
    ) -> tuple[date, date]:
        FinancePeriod.validate_duration(duration_months)
        if target_date < anchor_date:
            months = (
                (anchor_date.year - target_date.year) * 12
                + anchor_date.month
                - target_date.month
            )
            if cls.add_months(target_date, months) > anchor_date:
                months += 1
            bucket = -((months + duration_months - 1) // duration_months)
        else:
            months = (
                (target_date.year - anchor_date.year) * 12
                + target_date.month
                - anchor_date.month
            )
            candidate = cls.add_months(anchor_date, months)
            if candidate > target_date:
                months -= 1
            bucket = months // duration_months

        period_start = cls.add_months(anchor_date, bucket * duration_months)
        return cls.bounds_for(period_start, duration_months)

    @classmethod
    def resolved_for_configuration(
        cls, configuration: FinancePeriod, target_date: date
    ) -> ResolvedFinancePeriod:
        """Resolve one operating bucket and clamp it to configuration validity.

        Clamping is essential at configuration transitions. For example, a
        natural 15-Aug..14-Sep bucket becomes 15-Aug..31-Aug when a new
        configuration takes effect on 1-Sep. Therefore two configurations can
        never produce overlapping canonical operating periods at their boundary.
        """
        if not configuration.contains(target_date):
            raise ValueError("target_date is outside the FinancePeriod effective range.")

        natural_start, natural_end = cls.period_for_date(
            configuration.effective_from,
            target_date,
            configuration.duration_months,
        )
        period_start = max(natural_start, configuration.effective_from)
        period_end = natural_end
        if configuration.effective_to is not None:
            period_end = min(period_end, configuration.effective_to)

        if period_start > period_end or not (period_start <= target_date <= period_end):
            raise ValueError("Unable to resolve a canonical Finance period for target_date.")

        return ResolvedFinancePeriod(
            configuration_id=configuration.id,
            period_start=period_start,
            period_end=period_end,
        )
