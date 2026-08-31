from __future__ import annotations
from datetime import date, time
from typing import Optional
from sqlalchemy import Date, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class EmployeeWorkRegistration(Base, TimestampMixin):
    """Employee's proposed working blocks for a future month."""
    __tablename__ = "employee_work_registrations"

    STATUS_DRAFT = "DRAFT"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_CLOSED = "CLOSED"
    # APPROVED/REJECTED are retained as legacy values for old databases only.
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    VALID_STATUSES = {STATUS_DRAFT, STATUS_SUBMITTED, STATUS_CLOSED, STATUS_APPROVED, STATUS_REJECTED}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    work_type: Mapped[str] = mapped_column(String(60), nullable=False, default="WORK", server_default="WORK")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT, server_default=STATUS_DRAFT)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    employee = relationship("Employee", back_populates="work_registrations")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_employee_work_registration_employee_date", "employee_id", "work_date"),
        Index("ix_employee_work_registration_status", "employee_id", "status"),
    )
