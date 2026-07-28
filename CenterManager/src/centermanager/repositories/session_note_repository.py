# -*- coding: utf-8 -*-
"""
SessionNote repository - data access for SessionNote entity.
"""
from typing import Optional

from sqlalchemy.orm import Session

from centermanager.models.session_note import SessionNote
from centermanager.repositories.base import BaseRepository


class SessionNoteRepository(BaseRepository[SessionNote]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, SessionNote)

    def find_by_session(self, session_id: int) -> Optional[SessionNote]:
        """Get the note for a specific session."""
        return self._session.query(SessionNote).filter(
            SessionNote.session_id == session_id
        ).first()

    def exists_by_session(self, session_id: int) -> bool:
        """Check if a note exists for a session."""
        return self._session.query(SessionNote).filter(
            SessionNote.session_id == session_id
        ).first() is not None

    def add(self, note: SessionNote) -> SessionNote:
        self._session.add(note)
        return note

    def delete(self, note: SessionNote) -> None:
        self._session.delete(note)