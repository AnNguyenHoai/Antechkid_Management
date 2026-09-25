# -*- coding: utf-8 -*-
"""Historical tuition-pause ranges for one Enrollment."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.enrollment import Enrollment


class EnrollmentFreeze(Base, TimestampMixin):
    """Immutable-start freeze range; resume closes the range by setting end_session."""

    __tablename__ = "enrollment_freezes"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    start_session: Mapped[int] = mapped_column(Integer, nullable=False)
    end_session: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resume_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resumed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    enrollment: Mapped["Enrollment"] = relationship("Enrollment", back_populates="freezes")

    @property
    def is_open(self) -> bool:
        return self.end_session is None

    def contains_session(self, session_number: int) -> bool:
        number = int(session_number)
        return number >= self.start_session and (
            self.end_session is None or number <= self.end_session
        )
