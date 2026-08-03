# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, ForeignKey, DateTime, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from centermanager.database.base import Base


class ExpenseTimelineEvent(Base):
    __tablename__ = "expense_timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    __table_args__ = (
        Index("idx_expense_timeline_expense_id", "expense_id"),
        Index("idx_expense_timeline_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<ExpenseTimelineEvent(id={self.id}, expense_id={self.expense_id}, type='{self.event_type}')>"