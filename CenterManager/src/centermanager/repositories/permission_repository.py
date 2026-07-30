# -*- coding: utf-8 -*-
"""
Permission repository - data access for Permission entity.
"""
from typing import Optional, List

from sqlalchemy.orm import Session

from centermanager.models.permission import Permission
from centermanager.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Permission)

    def get_by_name(self, name: str) -> Optional[Permission]:
        """Get permission by name."""
        return self._session.query(Permission).filter(Permission.name == name).first()

    def get_by_category(self, category: str) -> List[Permission]:
        """Get all permissions in a category."""
        return self._session.query(Permission).filter(Permission.category == category).all()

    def list_all(self) -> List[Permission]:
        """Get all permissions."""
        return self._session.query(Permission).order_by(Permission.category, Permission.name).all()

    def add(self, permission: Permission) -> Permission:
        self._session.add(permission)
        return permission

    def delete(self, permission: Permission) -> None:
        self._session.delete(permission)