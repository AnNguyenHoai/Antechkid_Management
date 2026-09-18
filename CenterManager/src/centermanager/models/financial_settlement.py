from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class FinancialSettlement(Base, TimestampMixin):
    """Immutable-after-confirmation reconciliation snapshot for one FinancePeriod."""

    __tablename__ = "financial_settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finance_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    finance_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    opening_bank: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    income_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    income_bank: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    expense_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    expense_bank: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")

    expected_closing_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    expected_closing_bank: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    actual_closing_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    actual_closing_bank: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    difference_cash: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    difference_bank: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", server_default="DRAFT")
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    __table_args__ = (
        UniqueConstraint("finance_period_start", name="uq_financial_settlement_period_start"),
        CheckConstraint(
            "finance_period_end >= finance_period_start",
            name="ck_financial_settlement_period_range",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'CONFIRMED')",
            name="ck_financial_settlement_status",
        ),
    )

    STATUS_DRAFT = "DRAFT"
    STATUS_CONFIRMED = "CONFIRMED"

    @property
    def is_confirmed(self) -> bool:
        return self.status == self.STATUS_CONFIRMED
