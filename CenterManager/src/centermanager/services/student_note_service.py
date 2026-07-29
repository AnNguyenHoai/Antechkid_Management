# -*- coding: utf-8 -*-
"""
StudentNoteService - business logic for Note entity.
"""
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.note import Note, NoteType
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.note_repository import NoteRepository
from centermanager.services.timeline_service import TimelineService


class StudentNoteService:
    def __init__(self, session_factory: sessionmaker, timeline_service: Optional[TimelineService] = None):
        self._session_factory = session_factory
        self._timeline_service = timeline_service

    def _normalize_text(self, text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        stripped = text.strip()
        return stripped if stripped else None

    def _validate_note_type(self, note_type: str) -> str:
        valid = [e.value for e in NoteType]
        if note_type not in valid:
            raise ValueError(f"Invalid note type. Must be one of: {', '.join(valid)}")
        return note_type

    def create_note(
        self,
        student_id: int,
        note_type: str,
        content: str,
    ) -> Note:
        normalized_type = self._validate_note_type(note_type)
        normalized_content = self._normalize_text(content)
        if not normalized_content:
            raise ValueError("Note content cannot be empty.")

        with self._session_factory() as session:
            note = Note(
                student_id=student_id,
                note_type=normalized_type,
                content=normalized_content,
            )
            repo = NoteRepository(session)
            repo.add(note)
            session.commit()
            session.refresh(note)

            if self._timeline_service:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.NOTE_ADDED,
                    title=f"Note Added: {normalized_type}",
                    description=normalized_content[:100] + "..." if len(normalized_content) > 100 else normalized_content,
                    metadata={"note_id": note.id, "note_type": normalized_type},
                )
            return note

    def get_notes_for_student(self, student_id: int) -> List[Note]:
        with self._session_factory() as session:
            repo = NoteRepository(session)
            return repo.get_by_student(student_id)

    def get_note_by_id(self, note_id: int) -> Optional[Note]:   # NEW
        with self._session_factory() as session:
            repo = NoteRepository(session)
            return repo.get_by_id(note_id)

    def update_note(
        self,
        note_id: int,
        note_type: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Note:
        with self._session_factory() as session:
            repo = NoteRepository(session)
            note = repo.get_by_id(note_id)
            if note is None:
                raise ValueError(f"Note with id {note_id} not found.")

            if note_type is not None:
                note.note_type = self._validate_note_type(note_type)
            if content is not None:
                norm = self._normalize_text(content)
                if not norm:
                    raise ValueError("Note content cannot be empty.")
                note.content = norm

            session.commit()
            session.refresh(note)
            return note

    def delete_note(self, note_id: int) -> None:
        with self._session_factory() as session:
            repo = NoteRepository(session)
            note = repo.get_by_id(note_id)
            if note is None:
                raise ValueError(f"Note with id {note_id} not found.")
            repo.delete(note)
            session.commit()