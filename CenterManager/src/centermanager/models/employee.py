# -*- coding: utf-8 -*-
"""Employee domain aggregate."""
from __future__ import annotations
from datetime import date
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin
if TYPE_CHECKING:
    from centermanager.models.user import User

class Employee(Base, TimestampMixin):
    __tablename__ = "employees"
    STATUS_ACTIVE="ACTIVE"; STATUS_ON_LEAVE="ON_LEAVE"; STATUS_SUSPENDED="SUSPENDED"; STATUS_TERMINATED="TERMINATED"; STATUS_ARCHIVED="ARCHIVED"
    VALID_STATUSES={STATUS_ACTIVE,STATUS_ON_LEAVE,STATUS_SUSPENDED,STATUS_TERMINATED,STATUS_ARCHIVED}
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(30), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employment_status: Mapped[str] = mapped_column(String(30), nullable=False, default=STATUS_ACTIVE)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    user: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    __table_args__=(UniqueConstraint("employee_code", name="uq_employee_code"), UniqueConstraint("user_id", name="uq_employee_user"))
