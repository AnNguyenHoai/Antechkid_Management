# -*- coding: utf-8 -*-
"""
ClassTimeline repository - data access for ClassTimelineEvent.
"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.class_timeline_event import ClassTimelineEvent
from centermanager.repositories.base import BaseRepository


class ClassTimelineRepository(BaseRepository[ClassTimelineEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ClassTimelineEvent)

    def get_by_class(self, class_id: int, limit: Optional[int] = None) -> List[ClassTimelineEvent]:
        query = self._session.query(ClassTimelineEvent).filter(
            ClassTimelineEvent.class_id == class_id
        ).order_by(desc(ClassTimelineEvent.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def add(self, event: ClassTimelineEvent) -> ClassTimelineEvent:
        self._session.add(event)
        return event

    def delete(self, event: ClassTimelineEvent) -> None:
        self._session.delete(event)