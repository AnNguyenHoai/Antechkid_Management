# -*- coding: utf-8 -*-
from datetime import date, datetime
from typing import Optional

from sqlalchemy import String, Float, Date, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    # Funding source (FEAT-001). COMPANY: paid from a company wallet and
    # realized immediately. PERSONAL: an employee advanced the money; it is
    # not a company outflow until reimbursed from a company wallet.
    FUNDING_COMPANY = "COMPANY"
    FUNDING_PERSONAL = "PERSONAL"
    # payment_method placeholder for a not-yet-reimbursed personal advance.
    PERSONAL_PAYMENT_METHOD = "PERSONAL"

    id: Mapped[int] = mapped_column(primary_key=True)
    # FIN-03: client command identity survives retries and Git publication.
    # Nullable to preserve all historical entries; unique non-null keys
    # prevent duplicate financial postings from repeated Save commands.
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True, unique=True
    )

    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Pending")
    paid_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    finance_period_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("finance_periods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # NULL = legacy row not classified by migration 1e10a043 (closed period or
    # manual review); behaves exactly as before.
    funding_source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Date the employee spent the money (PERSONAL). After reimbursement,
    # payment_date is the reimbursement (realization) date.
    incurred_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, category={self.category}, amount={self.amount})>"
