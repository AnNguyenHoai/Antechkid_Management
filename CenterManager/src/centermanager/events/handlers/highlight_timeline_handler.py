# -*- coding: utf-8 -*-
"""
Timeline handler for StudentHighlight events.
"""
import logging
from datetime import datetime

from centermanager.events.event import Event, EventHandler
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.models.timeline_event import TimelineEventType
from centermanager.services.timeline_service import TimelineService
from centermanager.services.session_service import SessionService

logger = logging.getLogger(__name__)


class HighlightTimelineHandler(EventHandler):
    def __init__(
        self,
        timeline_service: TimelineService,
        session_service: SessionService,
    ) -> None:
        self._timeline_service = timeline_service
        self._session_service = session_service

    def handle(self, event: Event) -> None:
        if not isinstance(event, StudentHighlightCreated):
            return

        try:
            # Get session info to include in timeline metadata
            session = self._session_service.get_session(event.session_id)
            session_number = session.session_number
            scheduled_date = session.scheduled_date.strftime("%d/%m/%Y")

            # Build timeline description
            type_display = {
                "POSITIVE": "🌟",
                "SUPPORT": "🆘",
                "NEUTRAL": "📋",
            }.get(event.highlight_type, "📌")

            description = (
                f"{type_display} **{event.title}**\n"
                f"Session #{session_number} - {scheduled_date}\n"
                f"Type: {event.highlight_type}\n"
                f"{event.description or ''}"
            ).strip()

            # Create timeline entry
            self._timeline_service.log_event(
                student_id=event.student_id,
                event_type=TimelineEventType.SYSTEM,  # hoặc có thể dùng loại mới nếu cần
                title="Student Highlight",
                description=description,
                metadata={
                    "highlight_id": event.highlight_id,
                    "session_id": event.session_id,
                    "session_number": session_number,
                    "highlight_type": event.highlight_type,
                },
                created_by="system",
            )
            logger.info(f"Timeline entry created for highlight {event.highlight_id}, student {event.student_id}")
        except Exception as e:
            logger.exception(f"Failed to create timeline entry for highlight {event.highlight_id}: {e}")