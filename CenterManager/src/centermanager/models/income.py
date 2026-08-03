# -*- coding: utf-8 -*-
"""
Income model - records income transactions.
Now supports income not linked to student/class (nullable foreign keys).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Float, Date, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student
    from centermanager.models.class_ import Class


class Income(Base, TimestampMixin):
    __tablename__ = "incomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    
    # For student-related income: student_id and class_id can be NULL for other income sources
    student_id: Mapped[Optional[int]] = mapped_column(ForeignKey("students.id"), nullable=True)
    class_id: Mapped[Optional[int]] = mapped_column(ForeignKey("classes.id"), nullable=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    income_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_period: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    received_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships (optional)
    student: Mapped[Optional[Student]] = relationship("Student", lazy="selectin")
    class_: Mapped[Optional[Class]] = relationship("Class", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Income(id={self.id}, student_id={self.student_id}, amount={self.amount})>"