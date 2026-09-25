# -*- coding: utf-8 -*-
"""Immutable ledger for tuition refunds and non-cash credit adjustments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class TuitionAdjustment(Base, TimestampMixin):
    """First-class evidence for one tuition balance adjustment."""

    __tablename__ = "tuition_adjustments"
    __table_args__ = (
        CheckConstraint("kind IN ('REFUND', 'CREDIT_ADJUSTMENT')", name="ck_tuition_adjustment_kind"),
        CheckConstraint("amount > 0", name="ck_tuition_adjustment_amount_positive"),
        UniqueConstraint("idempotency_key", name="uq_tuition_adjustment_idempotency_key"),
        UniqueConstraint("linked_income_id", name="uq_tuition_adjustment_linked_income"),
    )

    KIND_REFUND = "REFUND"
    KIND_CREDIT = "CREDIT_ADJUSTMENT"

    id: Mapped[int] = mapped_column(primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    origin_income_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("incomes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    origin_adjustment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tuition_adjustments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    linked_income_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("incomes.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    adjustment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    wallet: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
