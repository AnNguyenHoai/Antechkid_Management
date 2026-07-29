# -*- coding: utf-8 -*-
"""
Note repository - data access for Note entity.
"""
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import desc

from centermanager.models.note import Note
from centermanager.repositories.base import BaseRepository


class NoteRepository(BaseRepository[Note]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Note)

    def get_by_student(self, student_id: int) -> List[Note]:
        return self._session.query(Note).filter(
            Note.student_id == student_id
        ).order_by(desc(Note.created_at)).all()

    def add(self, note: Note) -> Note:
        self._session.add(note)
        return note

    def delete(self, note: Note) -> None:
        self._session.delete(note)