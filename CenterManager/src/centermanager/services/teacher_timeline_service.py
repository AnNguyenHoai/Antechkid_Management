# -*- coding: utf-8 -*-
"""
TeacherTimelineService - log timeline events for teachers.
"""
import json
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.teacher_timeline_event import TeacherTimelineEvent, TeacherTimelineEventType
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider


class TeacherTimelineService:
    """Application service for teacher timeline records.

    Repository construction is delegated to ``RepositoryProvider`` while this
    service keeps ownership of the existing session/transaction boundary.
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        repository_provider: Optional[RepositoryProvider] = None,
    ) -> None:
        self._session_factory = session_factory
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def log_event(
        self,
        teacher_id: int,
        event_type: TeacherTimelineEventType,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> TeacherTimelineEvent:
        if isinstance(event_type, TeacherTimelineEventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)

        metadata_json = json.dumps(metadata) if metadata else None

        with self._session_factory() as session:
            event = TeacherTimelineEvent(
                teacher_id=teacher_id,
                event_type=event_type_str,
                title=title,
                description=description,
                metadata_json=metadata_json,
                created_by=created_by or "system",
            )
            repo = self._repository_provider.teacher_timeline(session)
            repo.add(event)
            session.commit()
            session.refresh(event)
            return event

    def get_teacher_timeline(self, teacher_id: int, limit: Optional[int] = None) -> List[TeacherTimelineEvent]:
        with self._session_factory() as session:
            repo = self._repository_provider.teacher_timeline(session)
            return repo.get_by_teacher(teacher_id, limit)

    def get_recent_events(self, limit: int = 10) -> List[TeacherTimelineEvent]:
        with self._session_factory() as session:
            repo = self._repository_provider.teacher_timeline(session)
            return repo.get_recent_events(limit=limit)
