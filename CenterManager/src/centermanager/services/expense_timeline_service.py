# -*- coding: utf-8 -*-
import json
from typing import Optional
from sqlalchemy.orm import sessionmaker

from centermanager.models.expense_timeline_event import ExpenseTimelineEvent
from centermanager.repositories.expense_timeline_repository import ExpenseTimelineRepository


class ExpenseTimelineService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def log_event(
        self,
        expense_id: int,
        event_type: str,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> ExpenseTimelineEvent:
        metadata_json = json.dumps(metadata) if metadata else None
        with self._session_factory() as session:
            event = ExpenseTimelineEvent(
                expense_id=expense_id,
                event_type=event_type,
                title=title,
                description=description,
                metadata_json=metadata_json,
                created_by=created_by or "system",
            )
            repo = ExpenseTimelineRepository(session)
            repo.add(event)
            session.commit()
            session.refresh(event)
            return event