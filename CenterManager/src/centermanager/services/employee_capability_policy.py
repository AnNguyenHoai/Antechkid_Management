"""Compatibility facade for Employee Workspace capability checks.

Authorization policy is centralized in ``AuthorizationService``. Employee
services may keep using this facade during migration. When a permission
service is supplied by an application boundary, this facade delegates to it;
production ``PermissionService`` itself delegates to the canonical
``AuthorizationService``.

The facade preserves one legacy Employee Workspace rule: an ``admin``
principal may access the Employee Workspace management capabilities that
historically had no persisted grant. This compatibility rule is deliberately
narrow and does not change the canonical AuthorizationService contract.
"""
from __future__ import annotations

from typing import Optional

from centermanager.core.capabilities import Capability
from centermanager.models.user import User


# Employee Workspace compatibility only. Do not add this to the canonical
# AuthorizationService implicit-role registry: EP-ARCH-02 intentionally keeps
# generic authorization fail-closed without a persisted grant.
_ADMIN_EMPLOYEE_WORKSPACE_COMPATIBILITY = frozenset({
    Capability.SCHEDULE_MANAGE.value,
})


class EmployeeCapabilityPolicy:
    """Compatibility predicates backed by the canonical authorization service."""

    @staticmethod
    def _canonical(capability: str) -> Capability:
        return Capability.from_value(capability)

    @classmethod
    def has(
        cls,
        user: Optional[User],
        capability: str,
        permission_service=None,
    ) -> bool:
        if user is None:
            return False
        canonical = cls._canonical(capability)

        # Preserve the pre-normalization Employee Workspace contract for the
        # privileged admin actor, while keeping the central authorization
        # service free of a generic admin -> everything bypass.
        role = getattr(user, "role", None)
        role_name = getattr(role, "name", None) if role is not None else None
        if role_name == "admin" and canonical.value in _ADMIN_EMPLOYEE_WORKSPACE_COMPATIBILITY:
            return True

        if permission_service is not None:
            return bool(permission_service.has_permission(canonical.value, user))
        from centermanager.services.authorization_service import AuthorizationService
        return AuthorizationService.allows(user, canonical)

    @classmethod
    def require(cls, user: Optional[User], capability: str, error_type, message=None):
        if not cls.has(user, capability):
            raise error_type(message or f"Permission '{capability}' is required.")

    @classmethod
    def has_all(cls, user: Optional[User], *capabilities: str) -> bool:
        return all(cls.has(user, capability) for capability in capabilities)
