# -*- coding: utf-8 -*-
"""
User repository - data access for User entity.
"""
from typing import Optional, List

from sqlalchemy.orm import Session, joinedload

from centermanager.models.user import User
from centermanager.models.role import Role
from centermanager.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username with role and permissions loaded."""
        return self._session.query(User).options(
            joinedload(User.role).joinedload(Role.permissions)
        ).filter(User.username == username).first()

    def get_by_id_with_role(self, user_id: int) -> Optional[User]:
        """Get user by ID with role and permissions loaded."""
        return self._session.query(User).options(
            joinedload(User.role).joinedload(Role.permissions)
        ).filter(User.id == user_id).first()

    def list_active(self) -> List[User]:
        """Get all active users."""
        return self._session.query(User).filter(User.is_active == True).all()

    def add(self, user: User) -> User:
        self._session.add(user)
        return user

    def delete(self, user: User) -> None:
        self._session.delete(user)