from __future__ import annotations

from typing import List

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class EmployeeWorkRegistration(Base, TimestampMixin):
    """One employee's availability registration for one planning period."""

    __tablename__ = "employee_work_registrations"

    STATUS_DRAFT = "DRAFT"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_ACCEPTED = "ACCEPTED"
    VALID_STATUSES = {STATUS_DRAFT, STATUS_SUBMITTED, STATUS_ACCEPTED}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    period_id: Mapped[int] = mapped_column(
        ForeignKey("employee_work_registration_periods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_DRAFT, server_default=STATUS_DRAFT
    )
    submitted_at: Mapped[object | None] = mapped_column(nullable=True)
    accepted_at: Mapped[object | None] = mapped_column(nullable=True)
    accepted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    employee = relationship("Employee", back_populates="work_registrations", lazy="joined")
    period = relationship("EmployeeWorkRegistrationPeriod", back_populates="registrations", lazy="joined")
    blocks: Mapped[List["EmployeeWorkRegistrationBlock"]] = relationship(
        "EmployeeWorkRegistrationBlock",
        back_populates="registration",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EmployeeWorkRegistrationBlock.work_date, EmployeeWorkRegistrationBlock.start_time",
    )
    accepted_by = relationship("User", foreign_keys=[accepted_by_user_id], lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "period_id",
            name="uq_employee_work_registration_employee_period",
        ),
    )


class EmployeeWorkRegistrationBlock(Base, TimestampMixin):
    """One availability time block inside a monthly employee registration."""

    __tablename__ = "employee_work_registration_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    registration_id: Mapped[int] = mapped_column(
        ForeignKey("employee_work_registrations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_date = mapped_column(nullable=False)
    start_time = mapped_column(nullable=False)
    end_time = mapped_column(nullable=False)
    work_type = mapped_column(String(60), nullable=False, default="WORK", server_default="WORK")
    notes = mapped_column(String(500), nullable=True)

    registration = relationship("EmployeeWorkRegistration", back_populates="blocks")
