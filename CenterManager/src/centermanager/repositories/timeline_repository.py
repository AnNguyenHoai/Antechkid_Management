# -*- coding: utf-8 -*-
"""
Timeline repository - data access for TimelineEvent.
"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.timeline_event import TimelineEvent
from centermanager.repositories.base import BaseRepository


class TimelineRepository(BaseRepository[TimelineEvent]):
    """Repository for TimelineEvent entity."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, TimelineEvent)

    def get_by_student(self, student_id: int, limit: Optional[int] = None) -> List[TimelineEvent]:
        """Get timeline events for a student, newest first."""
        query = self._session.query(TimelineEvent).filter(
            TimelineEvent.student_id == student_id
        ).order_by(desc(TimelineEvent.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def add(self, event: TimelineEvent) -> TimelineEvent:
        """Add a new timeline event."""
        self._session.add(event)
        return event

    def delete(self, event: TimelineEvent) -> None:
        """Delete a timeline event (used for testing/cleanup)."""
        self._session.delete(event)