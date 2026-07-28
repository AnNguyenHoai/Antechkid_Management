# -*- coding: utf-8 -*-
"""
Progress model - student skill/competency tracking.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class Progress(Base, TimestampMixin):
    __tablename__ = "progress"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="progress_records")

    def __repr__(self) -> str:
        return f"<Progress(id={self.id}, student_id={self.student_id}, category='{self.category}', value={self.value})>"