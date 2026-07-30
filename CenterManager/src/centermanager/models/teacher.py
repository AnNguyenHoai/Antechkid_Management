# -*- coding: utf-8 -*-
"""
Teacher model - manages teacher information.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.class_ import Class
    from centermanager.models.teacher_document import TeacherDocument
    from centermanager.models.teacher_timeline_event import TeacherTimelineEvent


class Teacher(Base, TimestampMixin):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    join_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    documents: Mapped[List[TeacherDocument]] = relationship(
        "TeacherDocument", back_populates="teacher", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[List[TeacherTimelineEvent]] = relationship(
        "TeacherTimelineEvent", back_populates="teacher", cascade="all, delete-orphan"
    )
    # Many-to-many with Class via teacher_assignments
    assigned_classes: Mapped[List[Class]] = relationship(
        "Class",
        secondary="teacher_assignments",
        back_populates="teachers",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Teacher(id={self.id}, code='{self.teacher_code}', name='{self.full_name}')>"