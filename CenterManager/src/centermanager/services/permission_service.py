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
from centermanager.repositories.employee_repository import EmployeeRepository
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


class RoleLifecycleError(ValueError):
    """Raised when a role operation would violate RBAC invariants."""
    pass


class PermissionService:
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def _audit(self, action: str, target=None, details=None) -> None:
        """Best-effort audit; administration must not fail because audit storage fails."""
        try:
            from centermanager.services.audit_service import AuditService
            module = "admin"
            target_type = "role" if isinstance(target, Role) else "user" if isinstance(target, User) else None
            AuditService(self._session_factory).record(action, module, target_type, getattr(target, "id", None), getattr(target, "name", None) or getattr(target, "username", None), details=details)
        except Exception:
            logger.exception("Audit logging failed for %s", action)

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

    # ===== Role & Permission Management =====

    def get_all_roles(self) -> List[Role]:
        with self._session_factory() as session:
            return RoleRepository(session).list_all_with_permissions()

    def get_role(self, role_id: int) -> Optional[Role]:
        with self._session_factory() as session:
            return RoleRepository(session).get_by_id_with_permissions(role_id)

    def get_permissions_by_category(self):
        with self._session_factory() as session:
            permissions = PermissionRepository(session).list_all()
            grouped = {}
            for permission in permissions:
                grouped.setdefault(permission.category or "other", []).append(permission)
            return grouped

    @staticmethod
    def _validate_role_name(name: str) -> None:
        if not name:
            raise ValueError("Role key is required.")
        normalized = name.replace("_", "")
        if not normalized.isalnum() or name != name.lower():
            raise ValueError("Role key must use lowercase letters, numbers and underscores only.")

    def _resolve_permissions(self, session, permission_names: Set[str]) -> List[Permission]:
        known = {p.name: p for p in PermissionRepository(session).list_all()}
        unknown = sorted(set(permission_names) - set(known))
        if unknown:
            raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
        return [known[name] for name in sorted(permission_names)]

    def create_role(self, name: str, display_name: str, description: Optional[str], permission_names: Set[str]) -> Role:
        name = name.strip(); display_name = display_name.strip()
        self._validate_role_name(name)
        if not display_name:
            raise ValueError("Display name is required.")
        with self._session_factory() as session:
            repo = RoleRepository(session)
            if repo.get_by_name(name) is not None:
                raise ValueError(f"Role '{name}' already exists.")
            role = Role(name=name, display_name=display_name, description=description, is_system=False)
            role.permissions = self._resolve_permissions(session, permission_names)
            repo.add(role); session.commit(); session.refresh(role)
            logger.info("Custom role created: %s", name)
            self._audit("ROLE_CREATED", role, {"permissions": sorted(permission_names)})
            return role

    def update_role(self, role_id: int, display_name: str, description: Optional[str], permission_names: Set[str]) -> Role:
        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Display name is required.")
        with self._session_factory() as session:
            role = RoleRepository(session).get_by_id_with_permissions(role_id)
            if role is None:
                raise ValueError("Role not found.")
            role.display_name = display_name
            role.description = description
            if role.is_system:
                current = role.permission_names
                if set(permission_names) != current:
                    raise RoleLifecycleError("Permissions of protected system roles cannot be changed.")
            else:
                role.permissions = self._resolve_permissions(session, permission_names)
            session.commit(); session.refresh(role)
            logger.info("Role updated: %s", role.name)
            self._audit("ROLE_UPDATED", role, {"permissions": sorted(permission_names)})
            return role

    def delete_role(self, role_id: int) -> None:
        with self._session_factory() as session:
            role = RoleRepository(session).get_by_id_with_permissions(role_id)
            if role is None:
                raise ValueError("Role not found.")
            if role.is_system:
                raise RoleLifecycleError("Protected system roles cannot be deleted.")
            if role.users:
                raise RoleLifecycleError("A role assigned to users cannot be deleted. Reassign its users first.")
            role_name = role.name; role_id = role.id
            RoleRepository(session).delete(role); session.commit()
            self._audit("ROLE_DELETED", None, {"role_id": role_id, "role": role_name})
            logger.info("Custom role deleted: %s", role_name)

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
            self._audit("USER_CREATED", user, {"role": role_name})
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
            self._audit("USER_UNLOCKED", user)
            return user

    def delete_user(self, user_id: int) -> None:
        with self._session_factory() as session:
            repo = UserRepository(session)
            user = repo.get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            self._ensure_not_current_user(user_id, "delete")
            self._ensure_not_last_admin(session, user, "delete")
            # An account is now the identity anchor for an Employee. Deleting it
            # would create an employee without an account, so lifecycle must use
            # deactivate/archive instead.
            from centermanager.models.employee import Employee
            linked_employee = session.query(Employee).filter(Employee.user_id == user_id).first()
            if linked_employee is not None:
                raise UserLifecycleError(
                    "This account is linked to employee "
                    f"{linked_employee.employee_code}. Deactivate the account instead of deleting it."
                )
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
            self._audit("USER_ACTIVATED" if active else "USER_DEACTIVATED", user)
            return user

    @staticmethod
    def _should_provision_employee(role_name: str) -> bool:
        """Only employee roles receive an Employee identity; admin is account-only."""
        return role_name != RoleDefinitions.ADMIN

    def create_user_with_temp_password(
        self, username: str, full_name: str, role_name: str,
        email: Optional[str] = None, phone: Optional[str] = None,
        temp_password: Optional[str] = None,
    ) -> User:
        from centermanager.security.password import hash_password
        import secrets, string
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
                password_hash=hash_password(temp_password),
                full_name=full_name,
                email=email,
                phone=phone,
                role_id=role.id,
                is_active=True,
                force_password_change=True,
                login_attempts=0,
            )
            user_repo.add(user)
            session.flush()

            employee = None
            if self._should_provision_employee(role_name):
                from centermanager.models.employee import Employee
                employee_repo = EmployeeRepository(session)
                next_number = (employee_repo.get_highest_employee_number() or 0) + 1
                employee = Employee(
                    employee_code=f"EMP-{next_number:05d}",
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    employment_status=Employee.STATUS_ACTIVE,
                    hire_date=None,
                    user_id=user.id,
                )
                employee_repo.add(employee)

            session.commit()
            session.refresh(user)
            if employee is not None:
                session.refresh(employee)
                logger.info(
                    "User created with employee profile: username=%s role=%s employee_id=%s",
                    username, role_name, employee.id,
                )
                self._audit("USER_CREATED", user, {"role": role_name, "employee_id": employee.id})
                user._employee_id = employee.id
            else:
                logger.info("User created without employee profile: username=%s role=%s", username, role_name)
                self._audit("USER_CREATED", user, {"role": role_name})
            user._temporary_password = temp_password
            return user

    def reset_user_password(self, user_id: int, temp_password: Optional[str] = None) -> str:
        from centermanager.security.password import hash_password
        import secrets, string
        with self._session_factory() as session:
            user = UserRepository(session).get_by_id_with_role(user_id)
            if user is None:
                raise UserNotFoundError(f"User {user_id} not found.")
            if temp_password is None:
                alphabet = string.ascii_letters + string.digits
                temp_password = "".join(secrets.choice(alphabet) for _ in range(10))
            user.password_hash = hash_password(temp_password)
            user.force_password_change = True
            user.login_attempts = 0
            user.locked_until = None
            session.commit()
            logger.info("Password reset for user_id=%s", user_id)
            self._audit("USER_PASSWORD_RESET", user)
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
            self._audit("USER_UPDATED", user)
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
