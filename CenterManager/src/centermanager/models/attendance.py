# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import time
from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, Time, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.session import Session
    from centermanager.models.student import Student


class AttendanceStatus(str, Enum):
    PRESENT = "Present"
    LATE = "Late"
    ABSENT = "Absent"
    EXCUSED = "Excused"

    @classmethod
    def choices(cls) -> list[str]:
        return [e.value for e in cls]

    @classmethod
    def display_name(cls, value: str) -> str:
        mapping = {
            "Present": "Present",
            "Late": "Late",
            "Absent": "Absent",
            "Excused": "Excused",
        }
        return mapping.get(value, value)


class Attendance(Base, TimestampMixin):
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AttendanceStatus.PRESENT.value)
    arrival_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    teacher_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="attendances")
    student: Mapped[Student] = relationship("Student", back_populates="attendances")

    __table_args__ = (
        UniqueConstraint('session_id', 'student_id', name='uq_attendance_session_student'),
        Index('idx_attendance_session_id', 'session_id'),
        Index('idx_attendance_student_id', 'student_id'),
    )

    def __repr__(self) -> str:
        return f"<Attendance(session_id={self.session_id}, student_id={self.student_id}, status='{self.status}')>"