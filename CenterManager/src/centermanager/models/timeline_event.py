# -*- coding: utf-8 -*-
"""
TimelineEvent model - student history log.
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
    from centermanager.models.student import Student


class TimelineEventType(str, Enum):
    STUDENT_CREATED = "StudentCreated"
    STUDENT_UPDATED = "StudentUpdated"
    PARENT_ADDED = "ParentAdded"
    PARENT_UPDATED = "ParentUpdated"
    PARENT_DELETED = "ParentDeleted"
    ASSESSMENT_CREATED = "AssessmentCreated"
    ASSESSMENT_UPDATED = "AssessmentUpdated"
    ASSESSMENT_DELETED = "AssessmentDeleted"
    PRODUCT_ADDED = "ProductAdded"
    ATTACHMENT_ADDED = "AttachmentAdded"
    NOTE_ADDED = "NoteAdded"
    DOCUMENT_UPLOADED = "DocumentUploaded"
    SYSTEM = "System"
    INCOME_CREATED = "IncomeCreated"
    INCOME_UPDATED = "IncomeUpdated"
    INCOME_DELETED = "IncomeDeleted"
    TUITION_COLLECTED = "TuitionCollected"
    ATTENDANCE_CREATED = "AttendanceCreated"
    ATTENDANCE_UPDATED = "AttendanceUpdated"
    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

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

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="timeline_events")

    __table_args__ = (
        Index("idx_timeline_events_student_id", "student_id"),
        Index("idx_timeline_events_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TimelineEvent(id={self.id}, student_id={self.student_id}, type='{self.event_type}')>"