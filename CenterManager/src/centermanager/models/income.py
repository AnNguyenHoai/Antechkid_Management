# -*- coding: utf-8 -*-
"""
Income model - records income transactions.

EP-FIN-06 adds an explicit lifecycle so voiding a financial transaction is
separate from soft deletion. Transaction identity (student/class/type) remains
stable after creation.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Float, Date, Text, ForeignKey, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student
    from centermanager.models.class_ import Class


class Income(Base, TimestampMixin):
    __tablename__ = "incomes"

    STATUS_ACTIVE = "ACTIVE"
    STATUS_VOIDED = "VOIDED"

    id: Mapped[int] = mapped_column(primary_key=True)

    student_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("students.id"), nullable=True
    )
    class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("classes.id"), nullable=True
    )

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    income_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_period: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    finance_period_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("finance_periods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    finance_period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    received_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Financial lifecycle.
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=STATUS_ACTIVE,
        server_default=STATUS_ACTIVE,
    )
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    voided_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Audit-safe tombstone. Rows are never hard-deleted by IncomeService.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    student: Mapped[Optional[Student]] = relationship("Student", lazy="selectin")
    class_: Mapped[Optional[Class]] = relationship("Class", lazy="selectin")

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None and self.status == self.STATUS_ACTIVE

    @property
    def is_voided(self) -> bool:
        return self.deleted_at is None and self.status == self.STATUS_VOIDED

    def __repr__(self) -> str:
        return (
            f"<Income(id={self.id}, student_id={self.student_id}, "
            f"amount={self.amount}, status={self.status})>"
        )
