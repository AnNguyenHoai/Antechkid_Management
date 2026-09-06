"""Canonical capability checks for Employee Workspace services.

The Employee Workspace uses operation-level capabilities as the authorization
contract. Roles are only a source of granted capabilities; they must not be
used as implicit write permission inside individual employee services.

Administrator is the single system-level exception: PermissionService defines
admin as having every permission, and this small policy mirrors that contract
without making each domain service reimplement role checks.
"""
from __future__ import annotations

from typing import Optional

from centermanager.models.permission import PermissionDefinitions
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User


class EmployeeCapabilityPolicy:
    """Pure capability predicates shared by Employee Workspace services."""

    @staticmethod
    def has(user: Optional[User], capability: str) -> bool:
        if user is None:
            return False
        if user.role and user.role.name == RoleDefinitions.ADMIN:
            return True

        # ``employee.update`` is the broader employee-management write
        # capability and therefore remains a valid superset for self-profile
        # updates. The reverse relationship is intentionally not allowed:
        # viewing a profile must never grant a write capability.
        if (
            capability == PermissionDefinitions.EMPLOYEE_UPDATE_SELF
            and user.has_permission(PermissionDefinitions.EMPLOYEE_UPDATE)
        ):
            return True

        return user.has_permission(capability)

    @classmethod
    def require(cls, user: Optional[User], capability: str, error_type, message=None):
        if not cls.has(user, capability):
            raise error_type(message or f"Permission '{capability}' is required.")

    @classmethod
    def has_all(cls, user: Optional[User], *capabilities: str) -> bool:
        return all(cls.has(user, capability) for capability in capabilities)
