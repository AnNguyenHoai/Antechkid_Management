# -*- coding: utf-8 -*-
"""Employee schedule domain models.

Recurring rules/exceptions are the reusable Schedule Template. Weekly schedule
entities represent the actual operational plan for one Monday-Sunday week.
"""
from __future__ import annotations
from datetime import date, time, timedelta
from typing import List, Optional
from sqlalchemy import Date, Integer, String, Time, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class EmployeeScheduleRule(Base, TimestampMixin):
    """Recurring template rule; Monday=0 ... Sunday=6."""

    __tablename__ = "employee_schedule_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
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
    """Date-specific override applied to the recurring schedule template."""

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


class EmployeeScheduleWeek(Base, TimestampMixin):
    """Operational schedule aggregate for one Monday-Sunday week.

    EP-EMP-WEEKLY-02 deliberately keeps the lifecycle at DRAFT. Publish/freeze,
    versioning and immutable history belong to EP-EMP-WEEKLY-03.
    """

    __tablename__ = "employee_schedule_weeks"
    STATUS_DRAFT = "DRAFT"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_DRAFT, server_default=STATUS_DRAFT
    )
    assignments: Mapped[List["EmployeeScheduleAssignment"]] = relationship(
        "EmployeeScheduleAssignment",
        back_populates="schedule_week",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EmployeeScheduleAssignment.work_date, EmployeeScheduleAssignment.start_time",
    )

    @property
    def week_end(self) -> date:
        return self.week_start + timedelta(days=6)


class EmployeeScheduleAssignment(Base, TimestampMixin):
    """One actual planned working interval inside a weekly schedule draft."""

    __tablename__ = "employee_schedule_assignments"

    SOURCE_MANUAL = "MANUAL"
    SOURCE_REGISTRATION = "REGISTRATION"
    SOURCE_TEMPLATE = "TEMPLATE"
    VALID_SOURCES = {SOURCE_MANUAL, SOURCE_REGISTRATION, SOURCE_TEMPLATE}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schedule_week_id: Mapped[int] = mapped_column(
        ForeignKey("employee_schedule_weeks.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SOURCE_MANUAL, server_default=SOURCE_MANUAL
    )
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    schedule_week = relationship("EmployeeScheduleWeek", back_populates="assignments")
    employee = relationship("Employee", lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "schedule_week_id",
            "employee_id",
            "work_date",
            "start_time",
            "end_time",
            name="uq_employee_schedule_assignment_interval",
        ),
        Index(
            "ix_employee_schedule_assignment_employee_date",
            "employee_id",
            "work_date",
        ),
        Index(
            "ix_employee_schedule_assignment_week_employee",
            "schedule_week_id",
            "employee_id",
        ),
    )


VALID_EXCEPTION_TYPES = {"OFF", "MODIFIED", "HOLIDAY", "LEAVE"}
