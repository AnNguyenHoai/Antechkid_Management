# -*- coding: utf-8 -*-
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.expense_timeline_event import ExpenseTimelineEvent
from centermanager.repositories.base import BaseRepository


class ExpenseTimelineRepository(BaseRepository[ExpenseTimelineEvent]):
    def __init__(self, session: Session):
        super().__init__(session, ExpenseTimelineEvent)

    def get_by_expense(self, expense_id: int, limit: Optional[int] = None) -> List[ExpenseTimelineEvent]:
        query = self._session.query(ExpenseTimelineEvent).filter(
            ExpenseTimelineEvent.expense_id == expense_id
        ).order_by(desc(ExpenseTimelineEvent.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def add(self, event: ExpenseTimelineEvent) -> ExpenseTimelineEvent:
        self._session.add(event)
        return event