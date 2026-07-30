# -*- coding: utf-8 -*-
"""
TeacherTimelineEvent - history log for teacher actions.
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
    from centermanager.models.teacher import Teacher


class TeacherTimelineEventType(str, Enum):
    TEACHER_CREATED = "TeacherCreated"
    TEACHER_UPDATED = "TeacherUpdated"
    TEACHER_ARCHIVED = "TeacherArchived"
    TEACHER_RESTORED = "TeacherRestored"
    TEACHER_ASSIGNED = "TeacherAssigned"
    TEACHER_UNASSIGNED = "TeacherUnassigned"
    DOCUMENT_UPLOADED = "DocumentUploaded"
    DOCUMENT_DELETED = "DocumentDeleted"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class TeacherTimelineEvent(Base):
    __tablename__ = "teacher_timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False)

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

    teacher: Mapped[Teacher] = relationship("Teacher", back_populates="timeline_events")

    __table_args__ = (
        Index("idx_teacher_timeline_teacher_id", "teacher_id"),
        Index("idx_teacher_timeline_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TeacherTimelineEvent(id={self.id}, teacher_id={self.teacher_id}, type='{self.event_type}')>"