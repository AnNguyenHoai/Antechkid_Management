# -*- coding: utf-8 -*-
"""
Student model - core entity for CenterManager.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.parent import Parent
    from centermanager.models.enrollment import Enrollment
    from centermanager.models.assessment import Assessment
    from centermanager.models.timeline_event import TimelineEvent
    from centermanager.models.student_product import StudentProduct
    from centermanager.models.progress import Progress
    from centermanager.models.attachment import Attachment
    from centermanager.models.student_highlight import StudentHighlight


class Student(Base, TimestampMixin):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    preferred_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    current_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    parents: Mapped[List[Parent]] = relationship(
        "Parent",
        back_populates="student",
        cascade="all, delete-orphan"
    )
    enrollments: Mapped[List[Enrollment]] = relationship("Enrollment", back_populates="student")
    assessments: Mapped[List[Assessment]] = relationship("Assessment", back_populates="student")
    timeline_events: Mapped[List[TimelineEvent]] = relationship("TimelineEvent", back_populates="student")
    products: Mapped[List[StudentProduct]] = relationship("StudentProduct", back_populates="student")
    progress_records: Mapped[List[Progress]] = relationship("Progress", back_populates="student")
    attachments: Mapped[List[Attachment]] = relationship("Attachment", back_populates="student")
    highlights: Mapped[List[StudentHighlight]] = relationship("StudentHighlight", back_populates="student")

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, code='{self.student_code}', name='{self.full_name}')>"