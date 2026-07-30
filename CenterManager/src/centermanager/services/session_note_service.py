# -*- coding: utf-8 -*-
"""
SessionNoteService - business logic for SessionNote entity.
"""
from typing import Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.session import SessionStatus
from centermanager.models.session_note import SessionNote, TeachingProgress, ClassAtmosphere
from centermanager.repositories.session_note_repository import SessionNoteRepository
from centermanager.services.session_service import SessionService, SessionNotFoundError


class SessionNoteServiceError(Exception):
    pass


class SessionNoteNotFoundError(SessionNoteServiceError):
    pass


class SessionNoteValidationError(SessionNoteServiceError):
    pass


class SessionNoteService:
    def __init__(self, session_factory: sessionmaker, session_service: SessionService) -> None:
        self._session_factory = session_factory
        self._session_service = session_service

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_enum(self, value: str, enum_class, field_name: str) -> str:
        valid = [e.value for e in enum_class]
        if value not in valid:
            raise SessionNoteValidationError(
                f"{field_name} must be one of: {', '.join(valid)}"
            )
        return value

    def create_note(
        self,
        session_id: int,
        teaching_progress: str,
        class_atmosphere: str,
        difficulties: Optional[str] = None,
        next_plan: Optional[str] = None,
        remark: Optional[str] = None,
        lesson_content: Optional[str] = None,
        homework: Optional[str] = None,
    ) -> SessionNote:
        # Validate session exists and is COMPLETED
        try:
            session = self._session_service.get_session(session_id)
        except SessionNotFoundError:
            raise SessionNoteValidationError("Session not found.")
        if session.status != SessionStatus.COMPLETED.value:
            raise SessionNoteValidationError(
                "Session Note can only be created for COMPLETED sessions."
            )

        # Check if note already exists
        with self._session_factory() as db_session:
            repo = SessionNoteRepository(db_session)
            if repo.exists_by_session(session_id):
                raise SessionNoteValidationError("A note already exists for this session.")

            # Validate enums
            teaching = self._validate_enum(teaching_progress, TeachingProgress, "Teaching Progress")
            atmosphere = self._validate_enum(class_atmosphere, ClassAtmosphere, "Class Atmosphere")

            # Normalize text fields
            norm_difficulties = self._normalize_text(difficulties)
            norm_next_plan = self._normalize_text(next_plan)
            norm_remark = self._normalize_text(remark)
            norm_lesson_content = self._normalize_text(lesson_content)
            norm_homework = self._normalize_text(homework)

            note = SessionNote(
                session_id=session_id,
                teaching_progress=teaching,
                class_atmosphere=atmosphere,
                difficulties=norm_difficulties,
                next_plan=norm_next_plan,
                remark=norm_remark,
                lesson_content=norm_lesson_content,
                homework=norm_homework,
            )
            repo.add(note)
            db_session.commit()
            db_session.refresh(note)
            return note

    def get_note(self, session_id: int) -> Optional[SessionNote]:
        with self._session_factory() as db_session:
            repo = SessionNoteRepository(db_session)
            return repo.find_by_session(session_id)

    def update_note(
        self,
        session_id: int,
        teaching_progress: Optional[str] = None,
        class_atmosphere: Optional[str] = None,
        difficulties: Optional[str] = None,
        next_plan: Optional[str] = None,
        remark: Optional[str] = None,
        lesson_content: Optional[str] = None,
        homework: Optional[str] = None,
    ) -> SessionNote:
        with self._session_factory() as db_session:
            repo = SessionNoteRepository(db_session)
            note = repo.find_by_session(session_id)
            if note is None:
                raise SessionNoteNotFoundError(f"No note found for session {session_id}")

            changed = []

            if teaching_progress is not None:
                new_val = self._validate_enum(teaching_progress, TeachingProgress, "Teaching Progress")
                if note.teaching_progress != new_val:
                    changed.append(f"teaching_progress: '{note.teaching_progress}' -> '{new_val}'")
                note.teaching_progress = new_val

            if class_atmosphere is not None:
                new_val = self._validate_enum(class_atmosphere, ClassAtmosphere, "Class Atmosphere")
                if note.class_atmosphere != new_val:
                    changed.append(f"class_atmosphere: '{note.class_atmosphere}' -> '{new_val}'")
                note.class_atmosphere = new_val

            if difficulties is not None:
                new_val = self._normalize_text(difficulties)
                old = note.difficulties or "(none)"
                new = new_val or "(none)"
                if old != new:
                    changed.append(f"difficulties: '{old}' -> '{new}'")
                note.difficulties = new_val

            if next_plan is not None:
                new_val = self._normalize_text(next_plan)
                old = note.next_plan or "(none)"
                new = new_val or "(none)"
                if old != new:
                    changed.append(f"next_plan: '{old}' -> '{new}'")
                note.next_plan = new_val

            if remark is not None:
                new_val = self._normalize_text(remark)
                old = note.remark or "(none)"
                new = new_val or "(none)"
                if old != new:
                    changed.append(f"remark: '{old}' -> '{new}'")
                note.remark = new_val

            if lesson_content is not None:
                new_val = self._normalize_text(lesson_content)
                old = note.lesson_content or "(none)"
                new = new_val or "(none)"
                if old != new:
                    changed.append(f"lesson_content: '{old}' -> '{new}'")
                note.lesson_content = new_val

            if homework is not None:
                new_val = self._normalize_text(homework)
                old = note.homework or "(none)"
                new = new_val or "(none)"
                if old != new:
                    changed.append(f"homework: '{old}' -> '{new}'")
                note.homework = new_val

            if not changed:
                return note

            db_session.commit()
            db_session.refresh(note)
            return note

    def delete_note(self, session_id: int) -> None:
        with self._session_factory() as db_session:
            repo = SessionNoteRepository(db_session)
            note = repo.find_by_session(session_id)
            if note is None:
                raise SessionNoteNotFoundError(f"No note found for session {session_id}")
            repo.delete(note)
            db_session.commit()