# -*- coding: utf-8 -*-
"""
Role repository - data access for Role entity.
"""
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload

from centermanager.models.role import Role
from centermanager.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Role)

    def get_by_name(self, name: str) -> Optional[Role]:
        """Get role by name with permissions loaded."""
        return self._session.query(Role).options(
            joinedload(Role.permissions)
        ).filter(Role.name == name).first()

    def get_by_id_with_permissions(self, role_id: int) -> Optional[Role]:
        """Get role by ID with permissions loaded."""
        return self._session.query(Role).options(
            joinedload(Role.permissions)
        ).filter(Role.id == role_id).first()

    def list_all_with_permissions(self) -> List[Role]:
        """List all roles with permissions loaded."""
        return self._session.query(Role).options(
            joinedload(Role.permissions)
        ).all()

    def add(self, role: Role) -> Role:
        self._session.add(role)
        return role

    def delete(self, role: Role) -> None:
        self._session.delete(role)