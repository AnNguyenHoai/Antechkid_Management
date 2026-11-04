# -*- coding: utf-8 -*-
"""Accounting voucher attached to an Income or Expense (FEAT-003, D-009).

Only metadata lives in SQLite. The file itself is stored immutably and
content-addressed under ``Attachment/Finance/<yyyy>/<mm>/<sha256>.<ext>`` so
the database stays small and Git stores every voucher exactly once.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base


class FinanceAttachment(Base):
    __tablename__ = "finance_attachments"
    __table_args__ = (
        Index("ix_finance_attachments_entity", "entity_type", "entity_id"),
    )

    ENTITY_INCOME = "INCOME"
    ENTITY_EXPENSE = "EXPENSE"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<FinanceAttachment(id={self.id}, {self.entity_type}#{self.entity_id}, {self.original_filename})>"
