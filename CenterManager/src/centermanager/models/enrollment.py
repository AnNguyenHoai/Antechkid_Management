# -*- coding: utf-8 -*-
"""
Enrollment model - student's class/course enrollment.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.student import Student
    from centermanager.models.class_ import Class


class Enrollment(Base, TimestampMixin):
    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    class_id: Mapped[Optional[int]] = mapped_column(ForeignKey("classes.id"), nullable=True)

    class_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    course_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    student: Mapped[Student] = relationship("Student", back_populates="enrollments")
    class_: Mapped[Optional[Class]] = relationship("Class", back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment(id={self.id}, student_id={self.student_id}, class='{self.class_name}')>"