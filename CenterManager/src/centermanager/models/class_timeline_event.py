# -*- coding: utf-8 -*-
"""
ClassTimelineEvent - history log for class actions.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base

if TYPE_CHECKING:
    from centermanager.models.class_ import Class


class ClassTimelineEventType(str, Enum):
    CLASS_CREATED = "ClassCreated"
    CLASS_UPDATED = "ClassUpdated"
    CLASS_ARCHIVED = "ClassArchived"
    CLASS_RESTORED = "ClassRestored"
    TEACHER_ASSIGNED = "TeacherAssigned"
    TEACHER_REPLACED = "TeacherReplaced"
    TEACHER_REMOVED = "TeacherRemoved"
    STUDENT_ENROLLED = "StudentEnrolled"
    STUDENT_REMOVED = "StudentRemoved"
    SCHEDULE_UPDATED = "ScheduleUpdated"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class ClassTimelineEvent(Base):
    __tablename__ = "class_timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id"), nullable=False)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=sa.text('(CURRENT_TIMESTAMP)')
    )

    class_: Mapped[Class] = relationship("Class", back_populates="timeline_events")

    __table_args__ = (
        Index("idx_class_timeline_class_id", "class_id"),
        Index("idx_class_timeline_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ClassTimelineEvent(id={self.id}, class_id={self.class_id}, type='{self.event_type}')>"