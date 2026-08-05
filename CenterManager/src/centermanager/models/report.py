# -*- coding: utf-8 -*-
"""
Report model - stores metadata for generated reports.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # relative path from runtime root
    report_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "manual", "automatic"
    trigger_event: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    generated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_student_id", "student_id"),
        Index("ix_reports_generated_at", "generated_at"),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, student_id={self.student_id}, type='{self.report_type}')>"