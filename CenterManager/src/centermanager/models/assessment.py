# -*- coding: utf-8 -*-
"""
Assessment model - student progress evaluation.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Date, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class AssessmentType(str, Enum):
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    FINAL = "Final"
    CUSTOM = "Custom"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class Assessment(Base, TimestampMixin):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

    # Core fields
    assessment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    assessment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    overall_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-5

    # Content
    strengths: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # giữ nguyên từ cũ
    improvements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)      # mới
    next_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    teacher_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy fields (giữ lại để không mất dữ liệu, nhưng không dùng trong UI mới)
    cycle_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    areas_for_improvement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student: Mapped[Student] = relationship("Student", back_populates="assessments")

    def __repr__(self) -> str:
        return f"<Assessment(id={self.id}, student_id={self.student_id}, date='{self.assessment_date}')>"