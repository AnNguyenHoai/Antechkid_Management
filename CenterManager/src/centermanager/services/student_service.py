# -*- coding: utf-8 -*-
"""
StudentService - business logic for Student entity.
Now integrated with TimelineService.
"""
from datetime import date, datetime, timezone
from typing import List, Optional, Any

from sqlalchemy.orm import Session, sessionmaker

from centermanager.models.student import Student
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.student_repository import StudentRepository
from centermanager.services.exceptions import (
    StudentNotFoundError,
    StudentValidationError,
    StudentAlreadyDeletedError,
    StudentNotDeletedError,
)
from centermanager.services.timeline_service import TimelineService

# Sentinel for "field not supplied"
UNSET = object()


class StudentService:
    """Application service for Student lifecycle operations."""

    def __init__(self, session_factory: sessionmaker, timeline_service: Optional[TimelineService] = None) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service

    def _utc_now(self) -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_full_name(self, full_name: Optional[str]) -> str:
        normalized = self._normalize_text(full_name)
        if not normalized:
            raise StudentValidationError("full_name is required and cannot be blank.")
        return normalized

    def _generate_student_code(self, session: Session) -> str:
        repo = StudentRepository(session)
        highest = repo.get_highest_hs_number()
        next_num = (highest or 0) + 1
        return f"HS{next_num:03d}"

    def create_student(
        self,
        full_name: str,
        preferred_name: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        gender: Optional[str] = None,
        status: Optional[str] = None,
        current_level: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Student:
        normalized_full_name = self._validate_full_name(full_name)
        normalized_preferred = self._normalize_text(preferred_name)
        normalized_gender = self._normalize_text(gender)
        normalized_level = self._normalize_text(current_level)
        normalized_notes = self._normalize_text(notes)
        normalized_status = self._normalize_text(status) or "ACTIVE"

        with self._session_factory() as session:
            try:
                student_code = self._generate_student_code(session)
                student = Student(
                    student_code=student_code,
                    full_name=normalized_full_name,
                    preferred_name=normalized_preferred,
                    date_of_birth=date_of_birth,
                    gender=normalized_gender,
                    status=normalized_status,
                    current_level=normalized_level,
                    notes=normalized_notes,
                )
                repo = StudentRepository(session)
                repo.add(student)
                session.commit()
                session.refresh(student)

                # Log timeline event
                if self._timeline_service:
                    self._timeline_service.log_event(
                        student_id=student.id,
                        event_type=TimelineEventType.STUDENT_CREATED,
                        title="Student Created",
                        description=f"{student.full_name} ({student.student_code}) was added.",
                        metadata={"student_code": student.student_code},
                    )

                return student
            except Exception:
                session.rollback()
                raise

    def get_student(self, student_id: int) -> Student:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            student = repo.get_by_id(student_id)
            if student is None or student.deleted_at is not None:
                raise StudentNotFoundError(f"Student id {student_id} not found or deleted.")
            return student

    def get_student_by_code(self, student_code: str) -> Student:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            student = repo.get_by_code(student_code)
            if student is None or student.deleted_at is not None:
                raise StudentNotFoundError(f"Student code {student_code} not found or deleted.")
            return student

    def get_student_including_deleted(self, student_id: int) -> Optional[Student]:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            return repo.get_by_id_including_deleted(student_id)

    def list_students(self) -> List[Student]:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            return repo.list_active()

    def update_student(
        self,
        student_id: int,
        full_name: Any = UNSET,
        preferred_name: Any = UNSET,
        date_of_birth: Any = UNSET,
        gender: Any = UNSET,
        status: Any = UNSET,
        current_level: Any = UNSET,
        notes: Any = UNSET,
    ) -> Student:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            student = repo.get_by_id_including_deleted(student_id)
            if student is None:
                raise StudentNotFoundError(f"Student id {student_id} not found.")

            changes = []  # list of strings "field: old -> new"

            if full_name is not UNSET:
                new_val = self._normalize_text(full_name)
                if new_val is None:
                    raise StudentValidationError("full_name cannot be cleared.")
                old_val = student.full_name
                if old_val != new_val:
                    changes.append(f"full_name: '{old_val}' -> '{new_val}'")
                student.full_name = new_val

            if preferred_name is not UNSET:
                new_val = self._normalize_text(preferred_name)
                old_val = student.preferred_name or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"preferred_name: '{old_val}' -> '{new_val or '(none)'}'")
                student.preferred_name = new_val

            if date_of_birth is not UNSET:
                old_val = student.date_of_birth.strftime("%d/%m/%Y") if student.date_of_birth else "(none)"
                new_val = date_of_birth  # có thể None hoặc date
                new_str = new_val.strftime("%d/%m/%Y") if new_val else "(none)"
                if old_val != new_str:
                    changes.append(f"date_of_birth: '{old_val}' -> '{new_str}'")
                student.date_of_birth = new_val

            if gender is not UNSET:
                new_val = self._normalize_text(gender)
                old_val = student.gender or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"gender: '{old_val}' -> '{new_val or '(none)'}'")
                student.gender = new_val

            if status is not UNSET:
                new_val = self._normalize_text(status) or "ACTIVE"
                old_val = student.status
                if old_val != new_val:
                    changes.append(f"status: '{old_val}' -> '{new_val}'")
                student.status = new_val

            if current_level is not UNSET:
                new_val = self._normalize_text(current_level)
                old_val = student.current_level or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"current_level: '{old_val}' -> '{new_val or '(none)'}'")
                student.current_level = new_val

            if notes is not UNSET:
                new_val = self._normalize_text(notes)
                old_val = student.notes or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"notes: '{old_val}' -> '{new_val or '(none)'}'")
                student.notes = new_val

            if not changes:
                # Không có gì thay đổi
                return student

            try:
                session.commit()
                session.refresh(student)

                if self._timeline_service:
                    description = "Updated: " + "; ".join(changes)
                    self._timeline_service.log_event(
                        student_id=student.id,
                        event_type=TimelineEventType.STUDENT_UPDATED,
                        title="Student Updated",
                        description=description,
                        metadata={"changes": changes},
                    )
                return student
            except Exception:
                session.rollback()
                raise

    def delete_student(self, student_id: int) -> None:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            student = repo.get_by_id_including_deleted(student_id)
            if student is None:
                raise StudentNotFoundError(f"Student id {student_id} not found.")
            if student.deleted_at is not None:
                raise StudentAlreadyDeletedError(f"Student id {student_id} is already deleted.")
            student.deleted_at = self._utc_now()
            try:
                session.commit()
                # Log timeline event
                if self._timeline_service:
                    self._timeline_service.log_event(
                        student_id=student.id,
                        event_type=TimelineEventType.STUDENT_UPDATED,  # or maybe a dedicated DELETE event?
                        title="Student Deleted",
                        description=f"{student.full_name} ({student.student_code}) was soft-deleted.",
                        metadata={"deleted": True},
                    )
            except Exception:
                session.rollback()
                raise

    def restore_student(self, student_id: int) -> None:
        with self._session_factory() as session:
            repo = StudentRepository(session)
            student = repo.get_by_id_including_deleted(student_id)
            if student is None:
                raise StudentNotFoundError(f"Student id {student_id} not found.")
            if student.deleted_at is None:
                raise StudentNotDeletedError(f"Student id {student_id} is not deleted.")
            student.deleted_at = None
            try:
                session.commit()
                if self._timeline_service:
                    self._timeline_service.log_event(
                        student_id=student.id,
                        event_type=TimelineEventType.STUDENT_UPDATED,
                        title="Student Restored",
                        description=f"{student.full_name} ({student.student_code}) was restored.",
                        metadata={"restored": True},
                    )
            except Exception:
                session.rollback()
                raise
    def search_students(self, query: str) -> List[Student]:
        """Search active students by multiple fields."""
        with self._session_factory() as session:
            repo = StudentRepository(session)
            return repo.search_students(query)