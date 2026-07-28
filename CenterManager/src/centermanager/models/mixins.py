# -*- coding: utf-8 -*-
"""
Shared model mixins for CenterManager.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy.orm import declared_attr, Mapped, mapped_column


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp fields.

    Usage:
        class MyModel(Base, TimestampMixin):
            __tablename__ = "my_table"
            ...
    """

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=False),
            nullable=False,
            server_default=func.current_timestamp(),
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            DateTime(timezone=False),
            nullable=False,
            server_default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
        )