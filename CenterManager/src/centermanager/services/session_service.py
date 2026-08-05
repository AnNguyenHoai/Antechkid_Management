# -*- coding: utf-8 -*-
"""
SessionService - business logic for Session entity (Academic Aggregate Root).
"""
from datetime import date, time
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.session import Session, SessionStatus
from centermanager.repositories.session_repository import SessionRepository
from centermanager.repositories.class_repository import ClassRepository
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.core.permission_guard import require_permission
from sqlalchemy.orm import selectinload
from centermanager.models.enrollment import Enrollment

class SessionServiceError(Exception):
    pass


class SessionNotFoundError(SessionServiceError):
    pass


class SessionValidationError(SessionServiceError):
    pass


class SessionService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    # ----- Helpers -----

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_title(self, title: Optional[str]) -> str:
        norm = self._normalize_text(title)
        if not norm:
            raise SessionValidationError("Title is required.")
        return norm

    def _validate_date(self, date_val: Optional[date]) -> date:
        if date_val is None:
            raise SessionValidationError("Lesson date is required.")
        return date_val

    def _validate_time(self, start_time: Optional[time], end_time: Optional[time]) -> tuple:
        if start_time is None or end_time is None:
            raise SessionValidationError("Start time and end time are required.")
        if start_time >= end_time:
            raise SessionValidationError("Start time must be before end time.")
        return start_time, end_time

    def _validate_status(self, status: str) -> str:
        valid = SessionStatus.choices()
        if status not in valid:
            raise SessionValidationError(f"Status must be one of: {', '.join(valid)}")
        return status

    def _get_next_session_number(self, class_id: int) -> int:
        with self._session_factory() as session:
            repo = SessionRepository(session)
            latest = repo.get_latest_session_number(class_id)
            return (latest or 0) + 1

    # ----- CRUD -----

    @require_permission("lesson.create")
    def create_session(
        self,
        class_id: int,
        title: str,
        scheduled_date: date,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        lesson_topic: Optional[str] = None,
        status: str = SessionStatus.SCHEDULED.value,
        actual_date: Optional[date] = None,
        teacher_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Session:
        # Validate
        norm_title = self._validate_title(title)
        norm_topic = self._normalize_text(lesson_topic)
        norm_note = self._normalize_text(note)
        scheduled_date = self._validate_date(scheduled_date)
        start_time, end_time = self._validate_time(start_time, end_time) if start_time and end_time else (None, None)
        status = self._validate_status(status)

        # Validate class exists
        with self._session_factory() as session:
            class_repo = ClassRepository(session)
            class_obj = class_repo.get_by_id(class_id)
            if class_obj is None:
                raise SessionValidationError(f"Class with id {class_id} not found.")

        session_number = self._get_next_session_number(class_id)

        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            session_obj = Session(
                class_id=class_id,
                session_number=session_number,
                title=norm_title,
                lesson_topic=norm_topic,
                scheduled_date=scheduled_date,
                actual_date=actual_date,
                start_time=start_time,
                end_time=end_time,
                status=status,
                teacher_id=teacher_id,
                note=norm_note,
            )
            repo.add(session_obj)
            db_session.commit()
            db_session.refresh(session_obj)

            # Log class timeline
            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=class_id,
                event_type="SessionCreated",
                title=f"Session {session_number} Created",
                description=f"Title: {norm_title}, Date: {scheduled_date}",
                metadata={"session_id": session_obj.id}
            )
            return session_obj

    @require_permission("lesson.view")
    def get_session(self, session_id: int) -> Session:
        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            session_obj = repo.get_by_id(session_id)
            if session_obj is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            return session_obj

    @require_permission("lesson.view")
    def get_sessions_for_class(self, class_id: int) -> List[Session]:
        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            return repo.get_by_class_ordered_desc(class_id)

    @require_permission("lesson.update")
    def update_session(
        self,
        session_id: int,
        title: Optional[str] = None,
        lesson_topic: Optional[str] = None,
        scheduled_date: Optional[date] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        actual_date: Optional[date] = None,
        status: Optional[str] = None,
        teacher_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Session:
        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            session_obj = repo.get_by_id(session_id)
            if session_obj is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")

            changes = []

            if title is not None:
                new_title = self._validate_title(title)
                if session_obj.title != new_title:
                    changes.append(f"title: '{session_obj.title}' -> '{new_title}'")
                session_obj.title = new_title

            if lesson_topic is not None:
                new_topic = self._normalize_text(lesson_topic)
                old = session_obj.lesson_topic or "(none)"
                new = new_topic or "(none)"
                if old != new:
                    changes.append(f"topic: '{old}' -> '{new}'")
                session_obj.lesson_topic = new_topic

            if scheduled_date is not None:
                self._validate_date(scheduled_date)
                old = session_obj.scheduled_date.strftime("%d/%m/%Y")
                new = scheduled_date.strftime("%d/%m/%Y")
                if old != new:
                    changes.append(f"date: {old} -> {new}")
                session_obj.scheduled_date = scheduled_date

            if start_time is not None and end_time is not None:
                self._validate_time(start_time, end_time)
                old = f"{session_obj.start_time}-{session_obj.end_time}" if session_obj.start_time else "None"
                new = f"{start_time}-{end_time}"
                if old != new:
                    changes.append(f"time: {old} -> {new}")
                session_obj.start_time = start_time
                session_obj.end_time = end_time
            elif start_time is not None:
                if session_obj.start_time != start_time:
                    changes.append(f"start_time: {session_obj.start_time} -> {start_time}")
                session_obj.start_time = start_time
            elif end_time is not None:
                if session_obj.end_time != end_time:
                    changes.append(f"end_time: {session_obj.end_time} -> {end_time}")
                session_obj.end_time = end_time

            if actual_date is not None:
                old = session_obj.actual_date.strftime("%d/%m/%Y") if session_obj.actual_date else "(none)"
                new = actual_date.strftime("%d/%m/%Y") if actual_date else "(none)"
                if old != new:
                    changes.append(f"actual_date: '{old}' -> '{new}'")
                session_obj.actual_date = actual_date

            if status is not None:
                new_status = self._validate_status(status)
                if session_obj.status != new_status:
                    changes.append(f"status: '{session_obj.status}' -> '{new_status}'")
                session_obj.status = new_status

            if teacher_id is not None:
                old = session_obj.teacher_id or "(none)"
                new = str(teacher_id) if teacher_id else "(none)"
                if old != new:
                    changes.append(f"teacher: {old} -> {new}")
                session_obj.teacher_id = teacher_id

            if note is not None:
                new_note = self._normalize_text(note)
                old = session_obj.note or "(none)"
                new = new_note or "(none)"
                if old != new:
                    changes.append(f"note: '{old}' -> '{new}'")
                session_obj.note = new_note

            if not changes:
                return session_obj

            db_session.commit()
            db_session.refresh(session_obj)

            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=session_obj.class_id,
                event_type="SessionUpdated",
                title=f"Session {session_obj.session_number} Updated",
                description="; ".join(changes),
                metadata={"session_id": session_obj.id}
            )
            return session_obj

    @require_permission("lesson.cancel")
    def cancel_session(self, session_id: int) -> Session:
        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            session_obj = repo.get_by_id(session_id)
            if session_obj is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            if session_obj.status == SessionStatus.CANCELLED.value:
                raise SessionValidationError("Session already cancelled.")
            session_obj.status = SessionStatus.CANCELLED.value
            db_session.commit()
            db_session.refresh(session_obj)

            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=session_obj.class_id,
                event_type="SessionCancelled",
                title=f"Session {session_obj.session_number} Cancelled",
                description=f"Session '{session_obj.title}' was cancelled.",
                metadata={"session_id": session_obj.id}
            )
            return session_obj

    @require_permission("lesson.delete")
    def delete_session(self, session_id: int) -> None:
        with self._session_factory() as db_session:
            repo = SessionRepository(db_session)
            session_obj = repo.get_by_id(session_id)
            if session_obj is None:
                raise SessionNotFoundError(f"Session {session_id} not found.")
            repo.delete(session_obj)
            db_session.commit()