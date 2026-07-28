# -*- coding: utf-8 -*-
"""
TimelineService - business logic for timeline events.
"""
import json
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.timeline_event import TimelineEvent, TimelineEventType
from centermanager.repositories.timeline_repository import TimelineRepository


class TimelineService:
    """Service for logging and retrieving timeline events."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def log_event(
        self,
        student_id: int,
        event_type: TimelineEventType,
        title: str,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
        created_by: Optional[str] = None,
    ) -> TimelineEvent:
        """
        Log a new timeline event.

        Args:
            student_id: ID of the student.
            event_type: Enum value.
            title: Short title of the event.
            description: Optional detailed description.
            metadata: Optional dict (will be JSON serialized).
            created_by: Optional username or system name.

        Returns:
            Created TimelineEvent object.
        """
        # Ensure event_type is a string value
        if isinstance(event_type, TimelineEventType):
            event_type_str = event_type.value
        else:
            event_type_str = str(event_type)

        metadata_json = json.dumps(metadata) if metadata else None

        with self._session_factory() as session:
            event = TimelineEvent(
                student_id=student_id,
                event_type=event_type_str,
                title=title,
                description=description,
                metadata_json=metadata_json,
                created_by=created_by or "system",
            )
            repo = TimelineRepository(session)
            repo.add(event)
            session.commit()
            session.refresh(event)
            return event

    def get_student_timeline(self, student_id: int, limit: Optional[int] = None) -> List[TimelineEvent]:
        """Get timeline events for a student, newest first."""
        with self._session_factory() as session:
            repo = TimelineRepository(session)
            return repo.get_by_student(student_id, limit)

    def delete_event(self, event_id: int) -> None:
        """Delete a specific event (for testing/cleanup)."""
        with self._session_factory() as session:
            repo = TimelineRepository(session)
            event = repo.get_by_id(event_id)
            if event:
                repo.delete(event)
                session.commit()