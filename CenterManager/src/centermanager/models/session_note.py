# -*- coding: utf-8 -*-
"""
SessionNote model - teacher's reflection for a completed session.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.session import Session


class TeachingProgress(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    EXCEEDED_PLAN = "EXCEEDED_PLAN"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class ClassAtmosphere(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NORMAL = "NORMAL"
    NEED_IMPROVEMENT = "NEED_IMPROVEMENT"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class SessionNote(Base, TimestampMixin):
    __tablename__ = "session_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True)

    teaching_progress: Mapped[str] = mapped_column(String(50), nullable=False)
    class_atmosphere: Mapped[str] = mapped_column(String(50), nullable=False)
    difficulties: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="note")

    __table_args__ = (
        UniqueConstraint('session_id', name='uq_session_note_session'),
    )

    def __repr__(self) -> str:
        return f"<SessionNote(id={self.id}, session_id={self.session_id})>"