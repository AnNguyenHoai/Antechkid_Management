# -*- coding: utf-8 -*-
"""
Expense model - records expense transactions.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import String, Float, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    paid_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Expense(id={self.id}, category={self.category}, amount={self.amount})>"