# -*- coding: utf-8 -*-
"""
ClassTimelineService - log timeline events for classes.
"""
import json
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.class_timeline_event import ClassTimelineEvent, ClassTimelineEventType
from centermanager.repositories.class_timeline_repository import ClassTimelineRepository


class ClassTimelineService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def log_event(
        self,
        class_id: int,
        event_type: ClassTimelineEventType,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> ClassTimelineEvent:
        if isinstance(event_type, ClassTimelineEventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)

        metadata_json = json.dumps(metadata) if metadata else None

        with self._session_factory() as session:
            event = ClassTimelineEvent(
                class_id=class_id,
                event_type=event_type_str,
                title=title,
                description=description,
                metadata_json=metadata_json,
                created_by=created_by or "system",
            )
            repo = ClassTimelineRepository(session)
            repo.add(event)
            session.commit()
            session.refresh(event)
            return event

    def get_class_timeline(self, class_id: int, limit: Optional[int] = None) -> List[ClassTimelineEvent]:
        with self._session_factory() as session:
            repo = ClassTimelineRepository(session)
            return repo.get_by_class(class_id, limit)