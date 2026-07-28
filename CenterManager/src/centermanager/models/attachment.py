# -*- coding: utf-8 -*-
"""
Attachment model - file reference for student documents.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    relative_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="attachments")

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, student_id={self.student_id}, file='{self.file_name}')>"