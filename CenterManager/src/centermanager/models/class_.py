# -*- coding: utf-8 -*-
"""
Class model - a course/class group.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.session import Session
    from centermanager.models.teacher import Teacher
    from centermanager.models.enrollment import Enrollment
    from centermanager.models.class_timeline_event import ClassTimelineEvent


class Class(Base, TimestampMixin):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    course: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    teacher: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # legacy
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=20)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Legacy compatibility shadow. Outstanding V2 no longer reads this field;
    # new tuition obligation is owned by the Enrollment snapshot/accrual model.
    fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    # Course/Tuition contract. Nullable is intentional for migrated historical
    # classes where duration/session evidence does not exist and must not be guessed.
    course_fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    planned_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sessions_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ===== XOÁ DÒNG lesson_sessions =====
    # Không còn relationship đến LessonSession

    # Relationships
    sessions: Mapped[List[Session]] = relationship("Session", back_populates="class_", cascade="all, delete-orphan")
    teachers: Mapped[List[Teacher]] = relationship(
        "Teacher",
        secondary="teacher_assignments",
        back_populates="assigned_classes",
        lazy="selectin"
    )
    enrollments: Mapped[List[Enrollment]] = relationship("Enrollment", back_populates="class_", cascade="all, delete-orphan")
    timeline_events: Mapped[List[ClassTimelineEvent]] = relationship(
        "ClassTimelineEvent", back_populates="class_", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Class(id={self.id}, name='{self.name}')>"

    @property
    def unit_fee(self) -> Optional[Decimal]:
        """Derived course price per planned session; never persisted.

        Returning ``None`` is an explicit unresolved historical-contract state.
        Decimal arithmetic avoids floating-point money rounding.
        """
        if self.course_fee is None or self.planned_sessions is None or self.planned_sessions <= 0:
            return None
        return Decimal(self.course_fee) / Decimal(self.planned_sessions)

    @property
    def has_course_contract(self) -> bool:
        return (
            self.start_date is not None
            and self.course_fee is not None
            and self.duration_months is not None
            and self.duration_months > 0
            and self.planned_sessions is not None
            and self.planned_sessions > 0
            and self.sessions_per_week is not None
            and self.sessions_per_week > 0
        )

    @property
    def student_count(self) -> int:
        return len(self.enrollments)

    @property
    def is_full(self) -> bool:
        if self.capacity is None:
            return False
        return self.student_count >= self.capacity

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE" and self.deleted_at is None
