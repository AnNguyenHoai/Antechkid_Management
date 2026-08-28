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


class UserLifecycleError(ValueError):
    """Raised when a user-management action would violate account invariants."""
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

    def _current_user_id(self) -> Optional[int]:
        current = get_current_user()
        return getattr(current, "id", None) if current is not None else None

    def _count_active_admins(self, session) -> int:
        admin_role = RoleRepository(session).get_by_name(RoleDefinitions.ADMIN)
        if admin_role is None:
            return 0
        return session.query(User).filter(
            User.role_id == admin_role.id,
            User.is_active == True,
        ).count()

    def _is_last_active_admin(self, session, user: User) -> bool:
        return bool(
            user.is_active
            and user.role is not None
            and user.role.name == RoleDefinitions.ADMIN
            and self._count_active_admins(session) <= 1
        )

    def _ensure_not_current_user(self, user_id: int, action: str) -> None:
        if self._current_user_id() == user_id:
            raise UserLifecycleError(f"You cannot {action} your own account.")

    def _ensure_not_last_admin(self, session, user: User, action: str) -> None:
        if self._is_last_active_admin(session, user):
            raise UserLifecycleError(f"Cannot {action} the last active administrator.")


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
        """Return all accounts, including inactive accounts, for administration."""
        with self._session_factory() as session:
            return session.query(User).all()

    def create_user(
        self,
        username: str,
        password_hash: str,
        full_name: str,
        email: Optional[str] = None,
        role_name: str = RoleDefinitions.RECEPTION,
    ) -> User:
        with self._session_factory() as session:
            repo = UserRepository(session)
            if repo.get_by_username(username) is not None:
                raise ValueError(f"Username '{username}' already exists.")
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
            role = RoleRepository(session).get_by_name(role_name)
            if role is None:
                raise ValueError(f"Role '{role_name}' not found.")
            if user.role is not None and user.role.name == RoleDefinitions.ADMIN and role.name != RoleDefinitions.ADMIN:
                self._ensure_not_current_user(user_id, "remove administrator access from")
                self._ensure_not_last_admin(session, user, "remove administrator access from")
            user.role_id = role.id
            session.commit()
            session.refresh(user)
            return user

    def delete_user(self, user_id: int) -> None:
        with self._session_factory() as session:
            repo = UserRepository(session)
            user = repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            self._ensure_not_current_user(user_id, "delete")
            self._ensure_not_last_admin(session, user, "delete")
            repo.delete(user)
            session.commit()

    def set_user_active(self, user_id: int, active: bool) -> User:
        with self._session_factory() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            if not active:
                self._ensure_not_current_user(user_id, "deactivate")
                self._ensure_not_last_admin(session, user, "deactivate")
            user.is_active = active
            session.commit()
            session.refresh(user)
            logger.info("User account status changed: user_id=%s active=%s", user_id, active)
            return user

    def create_user_with_temp_password(
        self, username: str, full_name: str, role_name: str,
        email: Optional[str] = None, phone: Optional[str] = None,
        temp_password: Optional[str] = None,
    ) -> User:
        import hashlib, secrets, string
        valid_roles = {
            RoleDefinitions.ADMIN, RoleDefinitions.TEACHER,
            RoleDefinitions.RECEPTION, RoleDefinitions.FINANCE,
            RoleDefinitions.MANAGER,
        }
        if role_name not in valid_roles:
            raise ValueError(f"Invalid role: {role_name}")

        with self._session_factory() as session:
            user_repo = UserRepository(session)
            if user_repo.get_by_username(username) is not None:
                raise ValueError(f"Username '{username}' already exists.")
            role = RoleRepository(session).get_by_name(role_name)
            if role is None:
                raise ValueError(f"Role '{role_name}' not found.")
            if temp_password is None:
                alphabet = string.ascii_letters + string.digits
                temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
            user = User(
                username=username,
                password_hash=hashlib.sha256(temp_password.encode()).hexdigest(),
                full_name=full_name,
                email=email,
                phone=phone,
                role_id=role.id,
                is_active=True,
                force_password_change=True,
                login_attempts=0,
            )
            user_repo.add(user)
            session.commit()
            session.refresh(user)
            logger.info("User created: username=%s role=%s", username, role_name)
            return user

    def reset_user_password(self, user_id: int, temp_password: Optional[str] = None) -> str:
        import hashlib, secrets, string
        with self._session_factory() as session:
            user = UserRepository(session).get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            if temp_password is None:
                alphabet = string.ascii_letters + string.digits
                temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
            user.password_hash = hashlib.sha256(temp_password.encode()).hexdigest()
            user.force_password_change = True
            user.login_attempts = 0
            user.locked_until = None
            session.commit()
            logger.info("Password reset for user_id=%s", user_id)
            return temp_password

    def update_user(self, user_id: int, full_name: Optional[str] = None,
                    email: Optional[str] = None, phone: Optional[str] = None,
                    role_name: Optional[str] = None) -> User:
        with self._session_factory() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")

            if full_name is not None:
                user.full_name = full_name
            if email is not None:
                user.email = email
            if phone is not None:
                user.phone = phone
            if role_name is not None:
                role_repo = RoleRepository(session)
                role = role_repo.get_by_name(role_name)
                if role is None:
                    raise ValueError(f"Role '{role_name}' not found.")
                if user.role is not None and user.role.name == RoleDefinitions.ADMIN and role.name != RoleDefinitions.ADMIN:
                    self._ensure_not_current_user(user_id, "remove administrator access from")
                    self._ensure_not_last_admin(session, user, "remove administrator access from")
                user.role_id = role.id

            session.commit()
            session.refresh(user)
            return user

    def unlock_user(self, user_id: int) -> User:
        with self._session_factory() as session:
            user_repo = UserRepository(session)
            user = user_repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            user.login_attempts = 0
            user.locked_until = None
            session.commit()
            session.refresh(user)
            return user