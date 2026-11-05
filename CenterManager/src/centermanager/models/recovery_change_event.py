"""Minimal immutable, transaction-bound recovery event (RV-02).

This is a *business operation index*, not an event-sourcing replay command.
No credentials, free-form notes, payment details or SQL parameters belong here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base


class RecoveryChangeEvent(Base):
    __tablename__ = "recovery_change_outbox"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    write_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    base_main_oid: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at_utc: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    module: Mapped[str] = mapped_column(String(60), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary_code: Mapped[str] = mapped_column(String(120), nullable=False)
    summary_args_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    schema_version: Mapped[int] = mapped_column(nullable=False, default=1)

    __table_args__ = (
        Index("ix_recovery_outbox_session", "write_session_id", "occurred_at_utc"),
        Index("ix_recovery_outbox_operation", "operation_id"),
    )
