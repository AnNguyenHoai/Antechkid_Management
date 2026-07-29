# -*- coding: utf-8 -*-
"""
ParentService - business logic for Parent entity.
Now integrated with TimelineService.
"""
from typing import List, Optional

from sqlalchemy.orm import sessionmaker

from centermanager.models.parent import Parent, RelationshipType
from centermanager.models.timeline_event import TimelineEventType
from centermanager.repositories.parent_repository import ParentRepository
from centermanager.services.exceptions import StudentServiceError, StudentValidationError
from centermanager.services.timeline_service import TimelineService


class ParentServiceError(StudentServiceError):
    pass


class ParentNotFoundError(ParentServiceError):
    pass


class ParentValidationError(ParentServiceError):
    pass


class ParentService:
    def __init__(self, session_factory: sessionmaker, timeline_service: Optional[TimelineService] = None) -> None:
        self._session_factory = session_factory
        self._timeline_service = timeline_service

    def _normalize_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def _validate_relationship(self, relationship: Optional[str]) -> Optional[str]:
        if relationship is None:
            return None
        norm = self._normalize_text(relationship)
        if norm is None:
            return None
        valid = [e.value for e in RelationshipType]
        if norm not in valid:
            raise ParentValidationError(
                f"Relationship must be one of: {', '.join(valid)}"
            )
        return norm

    def get_parents_for_student(self, student_id: int) -> List[Parent]:
        with self._session_factory() as session:
            repo = ParentRepository(session)
            return repo.get_by_student(student_id)

    def create_parent(
        self,
        student_id: int,
        name: str,
        relationship: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        occupation: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_primary_contact: bool = False,
    ) -> Parent:
        norm_name = self._normalize_text(name)
        if not norm_name:
            raise ParentValidationError("Parent name is required.")
        norm_relationship = self._validate_relationship(relationship)
        norm_phone = self._normalize_text(phone)
        norm_email = self._normalize_text(email)
        norm_occupation = self._normalize_text(occupation)
        norm_address = self._normalize_text(address)
        norm_notes = self._normalize_text(notes)

        with self._session_factory() as session:
            parent = Parent(
                student_id=student_id,
                name=norm_name,
                relation_type=norm_relationship,
                phone=norm_phone,
                email=norm_email,
                occupation=norm_occupation,
                address=norm_address,
                notes=norm_notes,
                is_primary_contact=is_primary_contact,
            )
            repo = ParentRepository(session)
            repo.add(parent)
            session.commit()
            session.refresh(parent)

            # Log timeline event
            if self._timeline_service:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.PARENT_ADDED,
                    title="Parent Added",
                    description=f"{norm_relationship or 'Guardian'}: {norm_name}",
                    metadata={"parent_id": parent.id},
                )

            return parent

    def update_parent(
        self,
        parent_id: int,
        name: Optional[str] = None,
        relationship: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        occupation: Optional[str] = None,
        address: Optional[str] = None,
        notes: Optional[str] = None,
        is_primary_contact: Optional[bool] = None,
    ) -> Parent:
        with self._session_factory() as session:
            repo = ParentRepository(session)
            parent = repo.get_by_id(parent_id)
            if parent is None:
                raise ParentNotFoundError(f"Parent id {parent_id} not found.")

            changes = []

            if name is not None:
                new_val = self._normalize_text(name)
                if not new_val:
                    raise ParentValidationError("Parent name cannot be empty.")
                old_val = parent.name
                if old_val != new_val:
                    changes.append(f"name: '{old_val}' -> '{new_val}'")
                parent.name = new_val

            if relationship is not None:
                new_val = self._validate_relationship(relationship) or "(none)"
                old_val = parent.relation_type or "(none)"
                if old_val != new_val:
                    changes.append(f"relationship: '{old_val}' -> '{new_val}'")
                parent.relation_type = new_val if new_val != "(none)" else None

            if phone is not None:
                new_val = self._normalize_text(phone) or "(none)"
                old_val = parent.phone or "(none)"
                if old_val != new_val:
                    changes.append(f"phone: '{old_val}' -> '{new_val}'")
                parent.phone = new_val if new_val != "(none)" else None

            if email is not None:
                new_val = self._normalize_text(email) or "(none)"
                old_val = parent.email or "(none)"
                if old_val != new_val:
                    changes.append(f"email: '{old_val}' -> '{new_val}'")
                parent.email = new_val if new_val != "(none)" else None

            if occupation is not None:
                new_val = self._normalize_text(occupation) or "(none)"
                old_val = parent.occupation or "(none)"
                if old_val != new_val:
                    changes.append(f"occupation: '{old_val}' -> '{new_val}'")
                parent.occupation = new_val if new_val != "(none)" else None

            if address is not None:
                new_val = self._normalize_text(address) or "(none)"
                old_val = parent.address or "(none)"
                if old_val != new_val:
                    changes.append(f"address: '{old_val}' -> '{new_val}'")
                parent.address = new_val if new_val != "(none)" else None

            if notes is not None:
                new_val = self._normalize_text(notes) or "(none)"
                old_val = parent.notes or "(none)"
                if old_val != new_val:
                    changes.append(f"notes: '{old_val}' -> '{new_val}'")
                parent.notes = new_val if new_val != "(none)" else None

            if is_primary_contact is not None:
                old_val = parent.is_primary_contact
                if old_val != is_primary_contact:
                    changes.append(f"primary_contact: {old_val} -> {is_primary_contact}")
                parent.is_primary_contact = is_primary_contact

            if not changes:
                return parent

            session.commit()
            session.refresh(parent)
            # Trong update_parent, sau khi commit và refresh:
            if self._timeline_service and changes:
                description = "Updated: " + "; ".join(changes)
                self._timeline_service.log_event(
                    student_id=parent.student_id,
                    event_type=TimelineEventType.PARENT_UPDATED,
                    title="Parent Updated",
                    description=description,
                    metadata={"changes": changes},
                )

            return parent

    def delete_parent(self, parent_id: int) -> None:
        with self._session_factory() as session:
            repo = ParentRepository(session)
            parent = repo.get_by_id(parent_id)
            if parent is None:
                raise ParentNotFoundError(f"Parent id {parent_id} not found.")
            student_id = parent.student_id
            name = parent.name
            repo.delete(parent)
            session.commit()

            # Log timeline event
            if self._timeline_service:
                self._timeline_service.log_event(
                    student_id=student_id,
                    event_type=TimelineEventType.PARENT_DELETED,
                    title="Parent Deleted",
                    description=f"Deleted {name or 'guardian'}",
                    metadata={"parent_id": parent_id},
                )