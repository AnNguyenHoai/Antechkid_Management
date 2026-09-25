# -*- coding: utf-8 -*-
"""Auditable transfer link between source and target Enrollment contracts."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from centermanager.models.enrollment import Enrollment


class EnrollmentTransfer(Base, TimestampMixin):
    """Immutable evidence of a class transfer and any explicit prepaid credit moved."""

    __tablename__ = "enrollment_transfers"
    __table_args__ = (
        UniqueConstraint("source_enrollment_id", name="uq_enrollment_transfer_source"),
        UniqueConstraint("idempotency_key", name="uq_enrollment_transfer_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    target_enrollment_id: Mapped[int] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False, unique=True, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    transferred_credit: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    source_balance_before: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    transferred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    source_enrollment: Mapped["Enrollment"] = relationship(
        "Enrollment", foreign_keys=[source_enrollment_id]
    )
    target_enrollment: Mapped["Enrollment"] = relationship(
        "Enrollment", foreign_keys=[target_enrollment_id]
    )
