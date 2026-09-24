# -*- coding: utf-8 -*-
"""
Enrollment model - student's class/course enrollment.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", server_default="ACTIVE")

    # Tuition contract snapshot. Nullable fields intentionally represent legacy
    # enrollments for which the old schema recorded no auditable contract terms.
    agreed_course_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    planned_sessions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unit_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 4), nullable=True)
    enrolled_from_session: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    enrolled_until_session: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )

    student: Mapped[Student] = relationship("Student", back_populates="enrollments")
    class_: Mapped[Optional[Class]] = relationship("Class", back_populates="enrollments")

    @property
    def has_tuition_contract(self) -> bool:
        """Whether this row has a complete auditable tuition snapshot."""
        return (
            self.agreed_course_fee is not None
            and self.planned_sessions is not None
            and self.planned_sessions > 0
            and self.unit_fee is not None
            and self.enrolled_from_session is not None
            and self.enrolled_from_session > 0
            and self.enrolled_until_session is not None
            and self.enrolled_until_session >= self.enrolled_from_session
        )

    @property
    def contracted_session_count(self) -> Optional[int]:
        if self.enrolled_from_session is None or self.enrolled_until_session is None:
            return None
        if self.enrolled_until_session < self.enrolled_from_session:
            return None
        return self.enrolled_until_session - self.enrolled_from_session + 1

    def __repr__(self) -> str:
        return f"<Enrollment(id={self.id}, student_id={self.student_id}, class='{self.class_name}')>"
