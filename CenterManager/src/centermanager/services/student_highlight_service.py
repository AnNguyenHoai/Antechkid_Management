"""StudentHighlightService - business logic for StudentHighlight."""
from typing import List, Optional
from sqlalchemy.orm import sessionmaker
from centermanager.models.student_highlight import StudentHighlight
from centermanager.repositories.provider import RepositoryProvider, SqlAlchemyRepositoryProvider
from centermanager.services.session_service import SessionService, SessionNotFoundError
from centermanager.validators.student_highlight_validator import StudentHighlightValidator
from centermanager.events.highlight_events import StudentHighlightCreated
from centermanager.events.event_bus import EventBus

class StudentHighlightService:
    def __init__(self, session_factory: sessionmaker, session_service: SessionService, event_bus: EventBus, repository_provider: RepositoryProvider | None = None) -> None:
        self._session_factory = session_factory
        self._session_service = session_service
        self._event_bus = event_bus
        self._repository_provider = repository_provider or SqlAlchemyRepositoryProvider()

    def create_highlight(self, session_id: int, student_id: int, highlight_type: str, title: str, description: Optional[str] = None) -> StudentHighlight:
        try:
            session = self._session_service.get_session(session_id)
        except SessionNotFoundError:
            raise ValueError("Session not found.")
        if not StudentHighlightValidator.validate_session_completed(session):
            raise ValueError("Session must be COMPLETED to add highlights.")
        class_id = session.class_id
        if not StudentHighlightValidator.validate_student_in_class(self._session_factory, student_id, class_id):
            raise ValueError("Student is not enrolled in this class.")
        validated_type = StudentHighlightValidator.validate_type(highlight_type)
        validated_title = StudentHighlightValidator.validate_title(title)
        desc_cleaned = description.strip() if description else None
        with self._session_factory() as db_session:
            repo = self._repository_provider.student_highlights(db_session)
            highlight = StudentHighlight(session_id=session_id, student_id=student_id, type=validated_type, title=validated_title, description=desc_cleaned)
            repo.add(highlight)
            db_session.commit()
            repo.refresh(highlight)
            self._event_bus.publish(StudentHighlightCreated(highlight_id=highlight.id, student_id=student_id, session_id=session_id, title=validated_title, highlight_type=validated_type, description=desc_cleaned))
            return highlight

    def get_highlights_for_session(self, session_id: int) -> List[StudentHighlight]:
        with self._session_factory() as db_session:
            return self._repository_provider.student_highlights(db_session).find_by_session(session_id)

    def get_highlights_for_student(self, student_id: int) -> List[StudentHighlight]:
        with self._session_factory() as db_session:
            return self._repository_provider.student_highlights(db_session).find_by_student(student_id)

    def update_highlight(self, highlight_id: int, highlight_type: Optional[str] = None, title: Optional[str] = None, description: Optional[str] = None) -> StudentHighlight:
        with self._session_factory() as db_session:
            repo = self._repository_provider.student_highlights(db_session)
            highlight = repo.get_by_id(highlight_id)
            if highlight is None: raise ValueError("Highlight not found.")
            if highlight_type is not None: highlight.type = StudentHighlightValidator.validate_type(highlight_type)
            if title is not None: highlight.title = StudentHighlightValidator.validate_title(title)
            if description is not None: highlight.description = description.strip() if description else None
            db_session.commit()
            repo.refresh(highlight)
            return highlight

    def delete_highlight(self, highlight_id: int) -> None:
        with self._session_factory() as db_session:
            repo = self._repository_provider.student_highlights(db_session)
            highlight = repo.get_by_id(highlight_id)
            if highlight is None: raise ValueError("Highlight not found.")
            repo.delete(highlight)
            db_session.commit()
