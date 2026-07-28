# -*- coding: utf-8 -*-
"""
Parent model - student's parent/guardian information.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student


class RelationshipType(str, Enum):
    """Enum for parent relationship types."""
    FATHER = "Father"
    MOTHER = "Mother"
    GUARDIAN = "Guardian"
    GRANDPARENT = "Grandparent"
    OTHER = "Other"

    @classmethod
    def choices(cls):
        return [e.value for e in cls]


class Parent(Base, TimestampMixin):
    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)

    # Fields
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    relation_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    occupation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    student: Mapped[Student] = relationship("Student", back_populates="parents")

    def __repr__(self) -> str:
        return f"<Parent(id={self.id}, student_id={self.student_id}, name='{self.name}')>"