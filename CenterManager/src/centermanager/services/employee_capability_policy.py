"""Canonical capability checks for Employee Workspace services.

The Employee Workspace uses operation-level capabilities as the authorization
contract. Roles are only a source of granted capabilities; they must not be
used as implicit write permission inside individual employee services.

Administrator is the single system-level exception: PermissionService defines
admin as having every permission, and this small policy mirrors that contract
without making each domain service reimplement role checks.

Manager compatibility is intentionally narrow. Existing employee and schedule
services historically treated the system Manager role as an operational
management identity. Those legacy grants are centralized here so callers do not
reimplement role checks themselves. Work Registration and Working Time remain
capability-driven and are not included in this compatibility set.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm.exc import DetachedInstanceError

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User


class EmployeeCapabilityPolicy:
    """Canonical capability predicates shared by Employee Workspace services."""

    MANAGER_IMPLICIT_CAPABILITIES = frozenset({
        PermissionDefinitions.EMPLOYEE_CREATE,
        PermissionDefinitions.EMPLOYEE_UPDATE,
        PermissionDefinitions.EMPLOYEE_ARCHIVE,
        PermissionDefinitions.SCHEDULE_MANAGE,
    })

    @staticmethod
    def _role_name(user: object) -> Optional[str]:
        """Read a lightweight principal's role without assuming ORM methods."""
        try:
            role = getattr(user, "role", None)
            return getattr(role, "name", None)
        except DetachedInstanceError:
            return None

    @classmethod
    def _manager_compatibility_grant(cls, user: object, capability: str) -> bool:
        return (
            cls._role_name(user) == RoleDefinitions.MANAGER
            and capability in cls.MANAGER_IMPLICIT_CAPABILITIES
        )

    @staticmethod
    def _direct_permission(user: object, capability: str) -> bool:
        """Evaluate a principal without requiring the SQLAlchemy User API.

        Production User instances expose ``has_permission``. Tests and other
        lightweight principals may expose a ``permissions`` set/list instead.
        """
        checker = getattr(user, "has_permission", None)
        if callable(checker):
            try:
                return bool(checker(capability))
            except DetachedInstanceError:
                return False

        try:
            permissions = getattr(user, "permissions", None)
        except DetachedInstanceError:
            return False

        if permissions is not None:
            try:
                return capability in permissions
            except TypeError:
                pass

        try:
            role = getattr(user, "role", None)
            permission_names = getattr(role, "permission_names", None)
            if permission_names is not None:
                return capability in permission_names
        except DetachedInstanceError:
            return False

        return False

    @classmethod
    def has(
        cls,
        user: Optional[User],
        capability: str,
        permission_service=None,
    ) -> bool:
        """Return whether ``user`` has ``capability`` without ORM coupling.

        ``permission_service`` is preferred when supplied because it is the
        canonical permission abstraction and supports lightweight principals.
        Direct User evaluation remains available for domain services that do not
        own a PermissionService dependency.
        """
        if user is None:
            return False

        role_name = cls._role_name(user)
        if role_name == RoleDefinitions.ADMIN:
            return True

        if cls._manager_compatibility_grant(user, capability):
            return True

        if permission_service is not None:
            try:
                if permission_service.has_permission(capability, user):
                    return True
            except (AttributeError, DetachedInstanceError):
                pass

            # ``employee.update`` is the broader employee-management write
            # capability and therefore remains a valid superset for self-profile
            # updates. The reverse relationship is intentionally not allowed:
            # viewing a profile must never grant a write capability.
            if capability == PermissionDefinitions.EMPLOYEE_UPDATE_SELF:
                try:
                    return bool(
                        permission_service.has_permission(
                            PermissionDefinitions.EMPLOYEE_UPDATE, user
                        )
                    )
                except (AttributeError, DetachedInstanceError):
                    return False
            return False

        # ``employee.update`` is the broader employee-management write
        # capability and therefore remains a valid superset for self-profile
        # updates. The reverse relationship is intentionally not allowed:
        # viewing a profile must never grant a write capability.
        if capability == PermissionDefinitions.EMPLOYEE_UPDATE_SELF:
            return cls._direct_permission(
                user, PermissionDefinitions.EMPLOYEE_UPDATE
            ) or cls._direct_permission(user, capability)

        return cls._direct_permission(user, capability)

    @classmethod
    def require(cls, user: Optional[User], capability: str, error_type, message=None):
        if not cls.has(user, capability):
            raise error_type(message or f"Permission '{capability}' is required.")

    @classmethod
    def has_all(cls, user: Optional[User], *capabilities: str) -> bool:
        return all(cls.has(user, capability) for capability in capabilities)
