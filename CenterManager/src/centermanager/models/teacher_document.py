# -*- coding: utf-8 -*-
"""
TeacherDocument model - documents uploaded for a teacher.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.teacher import Teacher


class TeacherDocument(Base, TimestampMixin):
    __tablename__ = "teacher_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # relative path
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    teacher: Mapped[Teacher] = relationship("Teacher", back_populates="documents")

    def __repr__(self) -> str:
        return f"<TeacherDocument(id={self.id}, teacher_id={self.teacher_id}, file='{self.file_name}')>"