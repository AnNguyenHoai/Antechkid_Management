"""Opt-in persisted monthly tuition contracts and immutable allocation evidence.

Legacy enrollments keep their original tuition policy until explicitly switched
by a future authorised application service.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base


class MonthlyTuitionPlanRecord(Base):
    __tablename__ = "monthly_tuition_plans"
    __table_args__ = (
        UniqueConstraint("class_id", "month", "version", name="uq_monthly_tuition_plan_version"),
        Index("uq_monthly_tuition_active_class_month", "class_id", "month",
              unique=True, sqlite_where=text("status = 'ACTIVE'")),
        CheckConstraint("monthly_fee_vnd >= 0", name="ck_monthly_plan_fee_nonnegative"),
        CheckConstraint("version > 0", name="ck_monthly_plan_version_positive"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED')", name="ck_monthly_plan_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), nullable=False, index=True)
    month: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_fee_vnd: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule_version: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    activated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class MonthlyTuitionAllocationRecord(Base):
    __tablename__ = "monthly_tuition_allocations"
    __table_args__ = (
        UniqueConstraint("plan_id", "session_id", name="uq_monthly_plan_session"),
        CheckConstraint("amount_vnd >= 0", name="ck_monthly_allocation_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("monthly_tuition_plans.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False)
    original_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_vnd: Mapped[int] = mapped_column(Integer, nullable=False)


class EnrollmentMonthlyTuitionTerm(Base):
    __tablename__ = "enrollment_monthly_tuition_terms"
    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_monthly_term_enrollment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    activated_by: Mapped[str] = mapped_column(String(100), nullable=False)


class MonthlyTuitionOutcomeRecord(Base):
    __tablename__ = "monthly_tuition_outcomes"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "session_id", "revision", name="uq_monthly_outcome_revision"),
        CheckConstraint("revision > 0", name="ck_monthly_outcome_revision_positive"),
        UniqueConstraint("idempotency_key", name="uq_monthly_outcome_idempotency"),
        CheckConstraint("outcome IN ('BILLABLE', 'RESCHEDULED', 'CENTRE_CANCELLED_NO_MAKEUP')", name="ck_monthly_outcome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="RESTRICT"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(100), nullable=False)
