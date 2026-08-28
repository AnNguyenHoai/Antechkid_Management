# -*- coding: utf-8 -*-
"""
TeacherService - business logic for Teacher entity.
"""
import re
from datetime import date, datetime, timezone
from typing import Optional, List, Any

from sqlalchemy.orm import Session, sessionmaker

from centermanager.models.teacher import Teacher
from centermanager.models.teacher_timeline_event import TeacherTimelineEventType
from centermanager.repositories.teacher_repository import TeacherRepository
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.events.event_bus import EventBus
from centermanager.events.teacher_events import TeacherCreated, TeacherUpdated, TeacherArchived, TeacherRestored


UNSET = object()


class TeacherServiceError(Exception):
    pass


class TeacherNotFoundError(TeacherServiceError):
    pass


class TeacherValidationError(TeacherServiceError):
    pass


class TeacherAlreadyDeletedError(TeacherServiceError):
    pass


class TeacherNotDeletedError(TeacherServiceError):
    pass


class TeacherService:
    def __init__(
        self,
        session_factory: sessionmaker,
        timeline_service: Optional[TeacherTimelineService] = None,
        event_bus: Optional[EventBus] = None
    ) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service
        self._event_bus = event_bus

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
            raise TeacherValidationError("Full name is required and cannot be blank.")
        return normalized

    def _validate_status(self, status: Optional[str]) -> str:
        normalized = (self._normalize_text(status) or Teacher.STATUS_ACTIVE).upper()
        if normalized not in Teacher.VALID_STATUSES:
            allowed = ", ".join(sorted(Teacher.VALID_STATUSES))
            raise TeacherValidationError(f"Invalid teacher status '{normalized}'. Allowed values: {allowed}.")
        return normalized

    def _validate_email(self, email: Optional[str]) -> Optional[str]:
        if email is None:
            return None
        normalized = self._normalize_text(email)
        if normalized and '@' not in normalized:
            raise TeacherValidationError("Invalid email format.")
        return normalized

    def _generate_teacher_code(self, session: Session) -> str:
        repo = TeacherRepository(session)
        highest = repo.get_highest_teacher_number()
        next_num = (highest or 0) + 1
        return f"TCH{next_num:03d}"

    # ===== CRUD =====

    def create_teacher(
        self,
        full_name: str,
        gender: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        join_date: Optional[date] = None,
        status: str = "ACTIVE",
    ) -> Teacher:
        norm_full_name = self._validate_full_name(full_name)
        norm_gender = self._normalize_text(gender)
        norm_phone = self._normalize_text(phone)
        norm_email = self._validate_email(email)
        norm_address = self._normalize_text(address)
        norm_status = self._validate_status(status)

        with self._session_factory() as session:
            teacher_code = self._generate_teacher_code(session)
            teacher = Teacher(
                teacher_code=teacher_code,
                full_name=norm_full_name,
                gender=norm_gender,
                date_of_birth=date_of_birth,
                phone=norm_phone,
                email=norm_email,
                address=norm_address,
                join_date=join_date or date.today(),
                status=norm_status,
            )
            repo = TeacherRepository(session)
            repo.add(teacher)
            session.commit()
            session.refresh(teacher)

            if self._timeline_service:
                self._timeline_service.log_event(
                    teacher_id=teacher.id,
                    event_type=TeacherTimelineEventType.TEACHER_CREATED,
                    title="Teacher Created",
                    description=f"{teacher.full_name} ({teacher.teacher_code}) was added.",
                    metadata={"teacher_code": teacher.teacher_code},
                )
            if self._event_bus:
                self._event_bus.publish(TeacherCreated(
                    teacher_id=teacher.id,
                    teacher_code=teacher.teacher_code,
                    teacher_name=teacher.full_name,
                ))
            return teacher

    def get_teacher(self, teacher_id: int) -> Teacher:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_id(teacher_id)
            if teacher is None or teacher.deleted_at is not None:
                raise TeacherNotFoundError(f"Teacher {teacher_id} not found or deleted.")
            return teacher

    def get_teacher_by_code(self, teacher_code: str) -> Teacher:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_code(teacher_code)
            if teacher is None:
                raise TeacherNotFoundError(f"Teacher code {teacher_code} not found.")
            return teacher

    def list_teachers(self) -> List[Teacher]:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            return repo.list_active()

    def search_teachers(self, query: str) -> List[Teacher]:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            return repo.search_teachers(query)

    def list_archived_teachers(self) -> List[Teacher]:
        with self._session_factory() as session:
            return TeacherRepository(session).list_archived()

    def get_archived_teacher(self, teacher_id: int) -> Teacher:
        with self._session_factory() as session:
            teacher = TeacherRepository(session).get_by_id(teacher_id)
            if teacher is None or teacher.deleted_at is None:
                raise TeacherNotFoundError(f"Archived teacher {teacher_id} not found.")
            return teacher

    def update_teacher(
        self,
        teacher_id: int,
        full_name: Any = UNSET,
        gender: Any = UNSET,
        date_of_birth: Any = UNSET,
        phone: Any = UNSET,
        email: Any = UNSET,
        address: Any = UNSET,
        join_date: Any = UNSET,
        status: Any = UNSET,
    ) -> Teacher:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_id(teacher_id)
            if teacher is None:
                raise TeacherNotFoundError(f"Teacher {teacher_id} not found.")
            if teacher.deleted_at is not None:
                raise TeacherAlreadyDeletedError(
                    f"Teacher {teacher_id} is archived and must be restored before editing."
                )

            changes = []

            if full_name is not UNSET:
                new_val = self._validate_full_name(full_name)
                old_val = teacher.full_name
                if old_val != new_val:
                    changes.append(f"full_name: '{old_val}' -> '{new_val}'")
                teacher.full_name = new_val

            if gender is not UNSET:
                new_val = self._normalize_text(gender)
                old_val = teacher.gender or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"gender: '{old_val}' -> '{new_val or '(none)'}'")
                teacher.gender = new_val

            if date_of_birth is not UNSET:
                old = teacher.date_of_birth.strftime("%d/%m/%Y") if teacher.date_of_birth else "(none)"
                new = date_of_birth.strftime("%d/%m/%Y") if date_of_birth else "(none)"
                if old != new:
                    changes.append(f"date_of_birth: '{old}' -> '{new}'")
                teacher.date_of_birth = date_of_birth

            if phone is not UNSET:
                new_val = self._normalize_text(phone)
                old_val = teacher.phone or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"phone: '{old_val}' -> '{new_val or '(none)'}'")
                teacher.phone = new_val

            if email is not UNSET:
                new_val = self._validate_email(email)
                old_val = teacher.email or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"email: '{old_val}' -> '{new_val or '(none)'}'")
                teacher.email = new_val

            if address is not UNSET:
                new_val = self._normalize_text(address)
                old_val = teacher.address or "(none)"
                if old_val != (new_val or "(none)"):
                    changes.append(f"address: '{old_val}' -> '{new_val or '(none)'}'")
                teacher.address = new_val

            if join_date is not UNSET:
                old = teacher.join_date.strftime("%d/%m/%Y") if teacher.join_date else "(none)"
                new = join_date.strftime("%d/%m/%Y") if join_date else "(none)"
                if old != new:
                    changes.append(f"join_date: '{old}' -> '{new}'")
                teacher.join_date = join_date

            if status is not UNSET:
                new_val = self._validate_status(status)
                old_val = teacher.status
                if old_val != new_val:
                    changes.append(f"status: '{old_val}' -> '{new_val}'")
                teacher.status = new_val

            if not changes:
                return teacher

            session.commit()
            session.refresh(teacher)

            if self._timeline_service:
                self._timeline_service.log_event(
                    teacher_id=teacher.id,
                    event_type=TeacherTimelineEventType.TEACHER_UPDATED,
                    title="Teacher Updated",
                    description="Updated: " + "; ".join(changes),
                    metadata={"changes": changes},
                )
            if self._event_bus:
                self._event_bus.publish(TeacherUpdated(
                    teacher_id=teacher.id,
                    teacher_code=teacher.teacher_code,
                    teacher_name=teacher.full_name,
                    changes=list(changes),
                ))
            return teacher

    def delete_teacher(self, teacher_id: int) -> None:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_id(teacher_id)
            if teacher is None:
                raise TeacherNotFoundError(f"Teacher {teacher_id} not found.")
            if teacher.deleted_at is not None:
                raise TeacherAlreadyDeletedError(f"Teacher {teacher_id} already deleted.")
            teacher.deleted_at = self._utc_now()
            session.commit()

            if self._timeline_service:
                self._timeline_service.log_event(
                    teacher_id=teacher.id,
                    event_type=TeacherTimelineEventType.TEACHER_ARCHIVED,
                    title="Teacher Archived",
                    description=f"{teacher.full_name} was archived.",
                )
            if self._event_bus:
                self._event_bus.publish(TeacherArchived(
                    teacher_id=teacher.id,
                    teacher_code=teacher.teacher_code,
                    teacher_name=teacher.full_name,
                ))

    def restore_teacher(self, teacher_id: int) -> None:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_id(teacher_id)
            if teacher is None:
                raise TeacherNotFoundError(f"Teacher {teacher_id} not found.")
            if teacher.deleted_at is None:
                raise TeacherNotDeletedError(f"Teacher {teacher_id} is not deleted.")
            teacher.deleted_at = None
            session.commit()

            if self._timeline_service:
                self._timeline_service.log_event(
                    teacher_id=teacher.id,
                    event_type=TeacherTimelineEventType.TEACHER_RESTORED,
                    title="Teacher Restored",
                    description=f"{teacher.full_name} was restored.",
                )
            if self._event_bus:
                self._event_bus.publish(TeacherRestored(
                    teacher_id=teacher.id,
                    teacher_code=teacher.teacher_code,
                    teacher_name=teacher.full_name,
                ))

    def get_teacher_with_details(self, teacher_id: int) -> Teacher:
        with self._session_factory() as session:
            repo = TeacherRepository(session)
            teacher = repo.get_by_id_with_relations(teacher_id)
            if teacher is None or teacher.deleted_at is not None:
                raise TeacherNotFoundError(f"Teacher {teacher_id} not found.")
            return teacher