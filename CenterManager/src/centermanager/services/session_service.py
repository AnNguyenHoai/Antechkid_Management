# -*- coding: utf-8 -*-
"""
SessionService - business logic for Session entity.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.session import Session, SessionStatus
from centermanager.repositories.session_repository import SessionRepository


class SessionServiceError(Exception):
    pass


class SessionNotFoundError(SessionServiceError):
    pass


class SessionValidationError(SessionServiceError):
    pass


class SessionService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_status(self, status: str) -> str:
        valid = [e.value for e in SessionStatus]
        if status not in valid:
            raise SessionValidationError(f"Status must be one of: {', '.join(valid)}")
        return status

    def create_session(
        self,
        class_id: int,
        title: str,
        scheduled_date: date,
        lesson_topic: Optional[str] = None,
        status: str = SessionStatus.SCHEDULED.value,
        actual_date: Optional[date] = None,
        teacher_id: Optional[int] = None,
    ) -> Session:
        norm_title = self._normalize_text(title)
        if not norm_title:
            raise SessionValidationError("Title is required.")
        if scheduled_date is None:
            raise SessionValidationError("Scheduled date is required.")

        norm_topic = self._normalize_text(lesson_topic)
        norm_status = self._validate_status(status)

        with self._session_factory() as session:
            repo = SessionRepository(session)
            # Generate session_number
            latest = repo.get_latest_session_number(class_id)
            next_number = (latest or 0) + 1

            session_obj = Session(
                class_id=class_id,
                session_number=next_number,
                title=norm_title,
                lesson_topic=norm_topic,
                scheduled_date=scheduled_date,
                actual_date=actual_date,
                status=norm_status,
                teacher_id=teacher_id,
            )
            repo.add(session_obj)
            session.commit()
            session.refresh(session_obj)
            return session_obj

    def get_session(self, session_id: int) -> Session:
        with self._session_factory() as session:
            repo = SessionRepository(session)
            obj = repo.get_by_id(session_id)
            if obj is None:
                raise SessionNotFoundError(f"Session id {session_id} not found.")
            return obj

    def get_sessions_for_class(self, class_id: int) -> List[Session]:
        with self._session_factory() as session:
            repo = SessionRepository(session)
            return repo.get_by_class_ordered_desc(class_id)

    def update_session(
        self,
        session_id: int,
        title: Optional[str] = None,
        lesson_topic: Optional[str] = None,
        scheduled_date: Optional[date] = None,
        actual_date: Optional[date] = None,
        status: Optional[str] = None,
        teacher_id: Optional[int] = None,
    ) -> Session:
        with self._session_factory() as session:
            repo = SessionRepository(session)
            obj = repo.get_by_id(session_id)
            if obj is None:
                raise SessionNotFoundError(f"Session id {session_id} not found.")

            changed = []

            if title is not None:
                norm = self._normalize_text(title)
                if not norm:
                    raise SessionValidationError("Title cannot be empty.")
                if obj.title != norm:
                    changed.append(f"title: '{obj.title}' -> '{norm}'")
                obj.title = norm

            if lesson_topic is not None:
                norm = self._normalize_text(lesson_topic)
                old = obj.lesson_topic or "(none)"
                new = norm or "(none)"
                if old != new:
                    changed.append(f"topic: '{old}' -> '{new}'")
                obj.lesson_topic = norm

            if scheduled_date is not None:
                if obj.scheduled_date != scheduled_date:
                    changed.append(f"date: {obj.scheduled_date.strftime('%d/%m/%Y')} -> {scheduled_date.strftime('%d/%m/%Y')}")
                obj.scheduled_date = scheduled_date

            if actual_date is not None:
                old = obj.actual_date.strftime('%d/%m/%Y') if obj.actual_date else "(none)"
                new = actual_date.strftime('%d/%m/%Y') if actual_date else "(none)"
                if old != new:
                    changed.append(f"actual_date: '{old}' -> '{new}'")
                obj.actual_date = actual_date

            if status is not None:
                norm_status = self._validate_status(status)
                if obj.status != norm_status:
                    changed.append(f"status: '{obj.status}' -> '{norm_status}'")
                obj.status = norm_status

            if teacher_id is not None:
                old = obj.teacher_id or "(none)"
                new = str(teacher_id) if teacher_id else "(none)"
                if old != new:
                    changed.append(f"teacher: {old} -> {new}")
                obj.teacher_id = teacher_id

            if not changed:
                return obj

            session.commit()
            session.refresh(obj)
            return obj

    def delete_session(self, session_id: int) -> None:
        with self._session_factory() as session:
            repo = SessionRepository(session)
            obj = repo.get_by_id(session_id)
            if obj is None:
                raise SessionNotFoundError(f"Session id {session_id} not found.")
            repo.delete(obj)
            session.commit()