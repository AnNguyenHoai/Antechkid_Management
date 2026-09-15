# -*- coding: utf-8 -*-
"""Employee schedule domain models: recurring weekly rules and date exceptions."""
from __future__ import annotations
from datetime import date, time
from typing import Optional
from sqlalchemy import Date, Integer, String, Time, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

class EmployeeScheduleRule(Base, TimestampMixin):
    __tablename__ = "employee_schedule_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # Monday=0 ... Sunday=6
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", server_default="ACTIVE")
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    employee = relationship("Employee", back_populates="schedule_rules")
    __table_args__ = (
        Index("ix_employee_schedule_rules_employee_day", "employee_id", "day_of_week"),
        Index("ix_employee_schedule_rules_effective", "employee_id", "effective_from", "effective_to"),
    )

class EmployeeScheduleException(Base, TimestampMixin):
    __tablename__ = "employee_schedule_exceptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    schedule_date: Mapped[date] = mapped_column(Date, nullable=False)
    exception_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    employee = relationship("Employee", back_populates="schedule_exceptions")
    __table_args__ = (
        UniqueConstraint("employee_id", "schedule_date", name="uq_employee_schedule_exception_date"),
        Index("ix_employee_schedule_exceptions_employee_date", "employee_id", "schedule_date"),
    )

VALID_EXCEPTION_TYPES = {"OFF", "MODIFIED", "HOLIDAY", "LEAVE"}
