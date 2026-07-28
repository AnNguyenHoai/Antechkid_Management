# -*- coding: utf-8 -*-
"""
StudentHighlight model - important observations per student during a session.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.session import Session
    from centermanager.models.student import Student


class HighlightType(str, Enum):
    POSITIVE = "POSITIVE"
    SUPPORT = "SUPPORT"
    NEUTRAL = "NEUTRAL"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]

    @classmethod
    def display_name(cls, value: str) -> str:
        mapping = {
            "POSITIVE": "Excellent performance",
            "SUPPORT": "Needs additional support",
            "NEUTRAL": "Observation only",
        }
        return mapping.get(value, value)


class StudentHighlight(Base, TimestampMixin):
    __tablename__ = "student_highlights"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="highlights")
    student: Mapped[Student] = relationship("Student", back_populates="highlights")

    def __repr__(self) -> str:
        return f"<StudentHighlight(id={self.id}, student_id={self.student_id}, session_id={self.session_id})>"