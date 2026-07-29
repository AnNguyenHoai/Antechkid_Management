# -*- coding: utf-8 -*-
"""Data access layer (Repository pattern)."""
from centermanager.repositories.base import BaseRepository
from centermanager.repositories.student_repository import StudentRepository
from .session_repository import SessionRepository
from .session_note_repository import SessionNoteRepository
from .student_highlight_repository import StudentHighlightRepository
from .enrollment_repository import EnrollmentRepository
from .class_repository import ClassRepository
from .note_repository import NoteRepository
from .document_repository import DocumentRepository

__all__ = [
    "BaseRepository",
    "StudentRepository",
    "SessionRepository",
    "SessionNoteRepository",
    "StudentHighlightRepository",
    "EnrollmentRepository",
    "ClassRepository",
    "NoteRepository",
    "DocumentRepository",
]