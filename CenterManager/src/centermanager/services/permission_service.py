# -*- coding: utf-8 -*-
"""
PermissionService - business logic for permission checking and management.
"""
import logging
from typing import Optional, List, Set

from sqlalchemy.orm import sessionmaker

from centermanager.models.user import User
from centermanager.models.role import Role, RoleDefinitions
from centermanager.models.permission import Permission, PermissionDefinitions
from centermanager.repositories.user_repository import UserRepository
from centermanager.repositories.role_repository import RoleRepository
from centermanager.repositories.permission_repository import PermissionRepository
from centermanager.core.current_user import get_current_user, set_current_user

logger = logging.getLogger(__name__)


class PermissionDeniedError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class PermissionService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    # ===== Permission Checking =====

    def has_permission(self, permission_name: str, user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        # Admin luôn có mọi quyền (bỏ qua kiểm tra chi tiết)
        if user.role and user.role.name == RoleDefinitions.ADMIN:
            return True
        return user.has_permission(permission_name)

    def has_any_permission(self, permission_names: List[str], user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        if user.role and user.role.name == RoleDefinitions.ADMIN:
            return True
        return user.has_any_permission(permission_names)

    def has_all_permissions(self, permission_names: List[str], user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        if user.role and user.role.name == RoleDefinitions.ADMIN:
            return True
        return user.has_all_permissions(permission_names)

    def require_permission(self, permission_name: str, user: Optional[User] = None) -> None:
        if not self.has_permission(permission_name, user):
            raise PermissionDeniedError(f"Permission '{permission_name}' is required.")

    def require_any_permission(self, permission_names: List[str], user: Optional[User] = None) -> None:
        if not self.has_any_permission(permission_names, user):
            raise PermissionDeniedError(f"Any of these permissions is required: {', '.join(permission_names)}")

    def get_user_permissions(self, user: Optional[User] = None) -> Set[str]:
        if user is None:
            user = get_current_user()
        if user is None or user.role is None:
            return set()
        return user.role.permission_names

    def get_user_role(self, user: Optional[User] = None) -> Optional[str]:
        if user is None:
            user = get_current_user()
        if user is None or user.role is None:
            return None
        return user.role.name

    def is_admin(self, user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        return user.is_admin

    def is_teacher(self, user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        return user.is_teacher

    def is_reception(self, user: Optional[User] = None) -> bool:
        if user is None:
            user = get_current_user()
        if user is None:
            return False
        return user.is_reception

    # ===== User Management =====

    def get_user(self, user_id: int) -> Optional[User]:
        with self._session_factory() as session:
            repo = UserRepository(session)
            return repo.get_by_id_with_role(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        with self._session_factory() as session:
            repo = UserRepository(session)
            return repo.get_by_username(username)

    def get_current_user(self) -> Optional[User]:
        return get_current_user()

    def set_current_user(self, user: User) -> None:
        set_current_user(user)

    def get_all_users(self) -> List[User]:
        with self._session_factory() as session:
            repo = UserRepository(session)
            return repo.list_active()

    def create_user(
        self,
        username: str,
        password_hash: str,
        full_name: str,
        email: Optional[str] = None,
        role_name: str = RoleDefinitions.RECEPTION,
    ) -> User:
        with self._session_factory() as session:
            role_repo = RoleRepository(session)
            role = role_repo.get_by_name(role_name)
            if role is None:
                raise ValueError(f"Role '{role_name}' not found.")

            user = User(
                username=username,
                password_hash=password_hash,
                full_name=full_name,
                email=email,
                role_id=role.id,
                is_active=True,
            )
            repo = UserRepository(session)
            repo.add(user)
            session.commit()
            session.refresh(user)
            return user

    def update_user_role(self, user_id: int, role_name: str) -> User:
        with self._session_factory() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")

            role_repo = RoleRepository(session)
            role = role_repo.get_by_name(role_name)
            if role is None:
                raise ValueError(f"Role '{role_name}' not found.")

            user.role_id = role.id
            session.commit()
            session.refresh(user)
            return user

    def delete_user(self, user_id: int) -> None:
        with self._session_factory() as session:
            repo = UserRepository(session)
            user = repo.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            repo.delete(user)
            session.commit()

    # ===== Permission Management =====

    def get_all_permissions(self) -> List[Permission]:
        with self._session_factory() as session:
            repo = PermissionRepository(session)
            return repo.list_all()

    def get_permissions_by_category(self, category: str) -> List[Permission]:
        with self._session_factory() as session:
            repo = PermissionRepository(session)
            return repo.get_by_category(category)