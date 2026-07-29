# -*- coding: utf-8 -*-
"""
Note model - internal notes for a student.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class NoteType(str, Enum):
    GENERAL = "General"
    BEHAVIOR = "Behavior"
    MEDICAL = "Medical"
    LEARNING = "Learning"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class Note(Base, TimestampMixin):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    note_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="notes_structured")

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, student_id={self.student_id}, type='{self.note_type}')>"