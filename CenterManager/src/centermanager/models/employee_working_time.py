from __future__ import annotations
from datetime import date, time
from typing import Optional
from sqlalchemy import Date, ForeignKey, Index, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class EmployeeWorkingTimeEntry(Base, TimestampMixin):
    """Actual employee working-time booking. One row represents one work block."""
    __tablename__ = "employee_working_time_entries"

    STATUS_OPEN = "OPEN"
    STATUS_BOOKED = "BOOKED"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_LOCKED = "LOCKED"
    VALID_STATUSES = {STATUS_OPEN, STATUS_BOOKED, STATUS_APPROVED, STATUS_REJECTED, STATUS_LOCKED}

    SOURCE_CHECK_IN = "CHECK_IN"
    SOURCE_MANUAL = "MANUAL"
    VALID_SOURCES = {SOURCE_CHECK_IN, SOURCE_MANUAL}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    work_type: Mapped[str] = mapped_column(String(60), nullable=False, default="WORK", server_default="WORK")
    source: Mapped[str] = mapped_column(String(20), nullable=False, default=SOURCE_MANUAL, server_default=SOURCE_MANUAL)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_BOOKED, server_default=STATUS_BOOKED)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    employee = relationship("Employee", back_populates="working_time_entries")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])

    __table_args__ = (
        Index("ix_employee_working_time_employee_date", "employee_id", "work_date"),
        Index("ix_employee_working_time_status", "employee_id", "status"),
    )
