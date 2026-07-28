# -*- coding: utf-8 -*-
"""
Parent repository - data access for Parent entity.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from centermanager.models.parent import Parent
from centermanager.repositories.base import BaseRepository


class ParentRepository(BaseRepository[Parent]):
    """Repository for Parent entity."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, Parent)

    def get_by_student(self, student_id: int) -> List[Parent]:
        """Get all parents for a given student."""
        return self._session.query(Parent).filter(
            Parent.student_id == student_id
        ).order_by(Parent.is_primary_contact.desc(), Parent.id).all()

    def get_by_id(self, parent_id: int) -> Optional[Parent]:
        """Get a single parent by ID."""
        return self._session.get(Parent, parent_id)

    def add(self, parent: Parent) -> Parent:
        """Add a new parent."""
        self._session.add(parent)
        return parent

    def delete(self, parent: Parent) -> None:
        """Delete a parent."""
        self._session.delete(parent)