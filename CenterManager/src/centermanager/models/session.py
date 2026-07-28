# -*- coding: utf-8 -*-
"""
Session model - a teaching session.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.class_ import Class
    from centermanager.models.session_note import SessionNote
    from centermanager.models.student_highlight import StudentHighlight


class SessionStatus(str, Enum):
    SCHEDULED = "Scheduled"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    POSTPONED = "Postponed"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class Session(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)

    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    lesson_topic: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=SessionStatus.SCHEDULED.value)
    teacher_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    class_: Mapped[Class] = relationship("Class", back_populates="sessions")
    note: Mapped[Optional[SessionNote]] = relationship("SessionNote", back_populates="session", uselist=False, cascade="all, delete-orphan")
    highlights: Mapped[List[StudentHighlight]] = relationship("StudentHighlight", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('class_id', 'session_number', name='uq_session_number_per_class'),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, class_id={self.class_id}, number={self.session_number})>"