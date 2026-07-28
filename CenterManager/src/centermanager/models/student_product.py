# -*- coding: utf-8 -*-
"""
StudentProduct model - student's project/product portfolio.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class StudentProduct(Base, TimestampMixin):
    __tablename__ = "student_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship("Student", back_populates="products")

    def __repr__(self) -> str:
        return f"<StudentProduct(id={self.id}, student_id={self.student_id}, title='{self.title}')>"