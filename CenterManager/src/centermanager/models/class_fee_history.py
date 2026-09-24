# -*- coding: utf-8 -*-
"""Effective-dated tuition fee history for Finance Outstanding semantics."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base
from centermanager.models.mixins import TimestampMixin


class ClassFeeHistory(Base, TimestampMixin):
    """Append-only tuition price version for one Class.

    Persistence is owned explicitly by ClassRepository/ClassService so fee
    history is written in the same application transaction as the Class change.
    The model intentionally has no mapper event side effects.
    """

    __tablename__ = "class_fee_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="CLASS_FEE_CHANGE",
        server_default="CLASS_FEE_CHANGE",
    )
