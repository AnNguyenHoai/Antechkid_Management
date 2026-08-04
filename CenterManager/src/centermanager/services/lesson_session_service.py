# -*- coding: utf-8 -*-
"""
LessonSessionService - business logic for LessonSession entity.
"""
from datetime import date, time
from typing import Optional, List

from sqlalchemy.orm import sessionmaker

from centermanager.models.lesson_session import LessonSession, LessonSessionStatus
from centermanager.repositories.lesson_session_repository import LessonSessionRepository
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.core.permission_guard import require_permission


class LessonSessionServiceError(Exception):
    pass


class LessonSessionNotFoundError(LessonSessionServiceError):
    pass


class LessonSessionValidationError(LessonSessionServiceError):
    pass


class LessonSessionService:
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_title(self, title: Optional[str]) -> str:
        norm = self._normalize_text(title)
        if not norm:
            raise LessonSessionValidationError("Title is required.")
        return norm

    def _validate_date(self, lesson_date: date) -> date:
        if lesson_date is None:
            raise LessonSessionValidationError("Lesson date is required.")
        return lesson_date

    def _validate_time(self, start_time: time, end_time: time) -> tuple:
        if start_time is None or end_time is None:
            raise LessonSessionValidationError("Start time and end time are required.")
        if start_time >= end_time:
            raise LessonSessionValidationError("Start time must be before end time.")
        return start_time, end_time

    def _validate_status(self, status: str) -> str:
        valid = LessonSessionStatus.choices()
        if status not in valid:
            raise LessonSessionValidationError(f"Status must be one of: {', '.join(valid)}")
        return status

    def _get_next_session_number(self, class_id: int) -> int:
        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            latest = repo.get_latest_session_number(class_id)
            return (latest or 0) + 1

    @require_permission("lesson.create")
    def create_session(
        self,
        class_id: int,
        title: str,
        lesson_date: date,
        start_time: time,
        end_time: time,
        topic: Optional[str] = None,
        teacher_id: Optional[int] = None,
        status: str = LessonSessionStatus.SCHEDULED.value,
        note: Optional[str] = None,
    ) -> LessonSession:
        norm_title = self._validate_title(title)
        norm_topic = self._normalize_text(topic)
        norm_note = self._normalize_text(note)
        lesson_date = self._validate_date(lesson_date)
        start_time, end_time = self._validate_time(start_time, end_time)
        status = self._validate_status(status)

        session_number = self._get_next_session_number(class_id)

        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            lesson = LessonSession(
                class_id=class_id,
                session_number=session_number,
                title=norm_title,
                topic=norm_topic,
                lesson_date=lesson_date,
                start_time=start_time,
                end_time=end_time,
                teacher_id=teacher_id,
                status=status,
                note=norm_note,
            )
            repo.add(lesson)
            session.commit()
            session.refresh(lesson)

            # Log class timeline
            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=class_id,
                event_type="LessonSessionCreated",
                title=f"Lesson Session {session_number} Created",
                description=f"Title: {norm_title}, Date: {lesson_date}",
                metadata={"session_id": lesson.id}
            )

            return lesson

    @require_permission("lesson.view")
    def get_session(self, session_id: int) -> LessonSession:
        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            lesson = repo.get_by_id(session_id)
            if lesson is None:
                raise LessonSessionNotFoundError(f"Session {session_id} not found.")
            return lesson

    @require_permission("lesson.view")
    def get_sessions_for_class(self, class_id: int) -> List[LessonSession]:
        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            return repo.get_by_class(class_id)

    @require_permission("lesson.update")
    def update_session(
        self,
        session_id: int,
        title: Optional[str] = None,
        topic: Optional[str] = None,
        lesson_date: Optional[date] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        teacher_id: Optional[int] = None,
        status: Optional[str] = None,
        note: Optional[str] = None,
    ) -> LessonSession:
        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            lesson = repo.get_by_id(session_id)
            if lesson is None:
                raise LessonSessionNotFoundError(f"Session {session_id} not found.")

            changes = []

            if title is not None:
                new_title = self._validate_title(title)
                if lesson.title != new_title:
                    changes.append(f"title: '{lesson.title}' -> '{new_title}'")
                lesson.title = new_title

            if topic is not None:
                new_topic = self._normalize_text(topic)
                old = lesson.topic or "(none)"
                new = new_topic or "(none)"
                if old != new:
                    changes.append(f"topic: '{old}' -> '{new}'")
                lesson.topic = new_topic

            if lesson_date is not None:
                self._validate_date(lesson_date)
                if lesson.lesson_date != lesson_date:
                    changes.append(f"date: {lesson.lesson_date} -> {lesson_date}")
                lesson.lesson_date = lesson_date

            if start_time is not None and end_time is not None:
                self._validate_time(start_time, end_time)
                if lesson.start_time != start_time or lesson.end_time != end_time:
                    changes.append(f"time: {lesson.start_time}-{lesson.end_time} -> {start_time}-{end_time}")
                lesson.start_time = start_time
                lesson.end_time = end_time
            elif start_time is not None:
                if lesson.start_time != start_time:
                    changes.append(f"start_time: {lesson.start_time} -> {start_time}")
                lesson.start_time = start_time
            elif end_time is not None:
                if lesson.end_time != end_time:
                    changes.append(f"end_time: {lesson.end_time} -> {end_time}")
                lesson.end_time = end_time

            if teacher_id is not None:
                old = lesson.teacher_id or "(none)"
                new = str(teacher_id) if teacher_id else "(none)"
                if old != new:
                    changes.append(f"teacher: {old} -> {new}")
                lesson.teacher_id = teacher_id

            if status is not None:
                new_status = self._validate_status(status)
                if lesson.status != new_status:
                    changes.append(f"status: '{lesson.status}' -> '{new_status}'")
                lesson.status = new_status

            if note is not None:
                new_note = self._normalize_text(note)
                old = lesson.note or "(none)"
                new = new_note or "(none)"
                if old != new:
                    changes.append(f"note: '{old}' -> '{new}'")
                lesson.note = new_note

            if not changes:
                return lesson

            session.commit()
            session.refresh(lesson)

            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=lesson.class_id,
                event_type="LessonSessionUpdated",
                title=f"Lesson Session {lesson.session_number} Updated",
                description="; ".join(changes),
                metadata={"session_id": lesson.id}
            )

            return lesson

    @require_permission("lesson.cancel")
    def cancel_session(self, session_id: int) -> LessonSession:
        with self._session_factory() as session:
            repo = LessonSessionRepository(session)
            lesson = repo.get_by_id(session_id)
            if lesson is None:
                raise LessonSessionNotFoundError(f"Session {session_id} not found.")
            if lesson.status == LessonSessionStatus.CANCELLED.value:
                raise LessonSessionValidationError("Session already cancelled.")
            lesson.status = LessonSessionStatus.CANCELLED.value
            session.commit()
            session.refresh(lesson)

            timeline_service = ClassTimelineService(self._session_factory)
            timeline_service.log_event(
                class_id=lesson.class_id,
                event_type="LessonSessionCancelled",
                title=f"Lesson Session {lesson.session_number} Cancelled",
                description=f"Session {lesson.title} was cancelled.",
                metadata={"session_id": lesson.id}
            )

            return lesson