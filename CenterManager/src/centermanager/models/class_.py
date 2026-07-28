# -*- coding: utf-8 -*-
"""
Class model - a course/class group.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.session import Session


class Class(Base, TimestampMixin):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    course: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    teacher: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    sessions: Mapped[List[Session]] = relationship("Session", back_populates="class_", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Class(id={self.id}, name='{self.name}')>"