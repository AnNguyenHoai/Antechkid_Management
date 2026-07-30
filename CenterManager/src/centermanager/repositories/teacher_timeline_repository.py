# -*- coding: utf-8 -*-
"""
TeacherTimeline repository - data access for TeacherTimelineEvent.
"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.teacher_timeline_event import TeacherTimelineEvent
from centermanager.repositories.base import BaseRepository


class TeacherTimelineRepository(BaseRepository[TeacherTimelineEvent]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, TeacherTimelineEvent)

    def get_by_teacher(self, teacher_id: int, limit: Optional[int] = None) -> List[TeacherTimelineEvent]:
        query = self._session.query(TeacherTimelineEvent).filter(
            TeacherTimelineEvent.teacher_id == teacher_id
        ).order_by(desc(TeacherTimelineEvent.created_at))
        if limit:
            query = query.limit(limit)
        return query.all()

    def add(self, event: TeacherTimelineEvent) -> TeacherTimelineEvent:
        self._session.add(event)
        return event

    def delete(self, event: TeacherTimelineEvent) -> None:
        self._session.delete(event)