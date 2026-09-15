"""Centralized authorization decisions for application capabilities."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Iterable, Any

from centermanager.core.capabilities import (
    Capability,
    ADMIN_ONLY_CAPABILITIES,
    IMPLICIT_ROLE_CAPABILITIES,
    IMPLIED_CAPABILITIES,
    LEGACY_CAPABILITY_ALIASES,
)
from centermanager.models.role import RoleDefinitions


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class AuthorizationContext:
    """Optional request context for a capability decision.

    Resource and edit-session checks remain separate application/domain
    invariants. Context never grants a capability by itself.
    """

    actor_id: Optional[int] = None
    workspace: Optional[str] = None
    resource_id: Optional[int] = None
    edit_session_id: Optional[str] = None
    platform_mode: Optional[str] = None


class AuthorizationService:
    """Single entry point for capability-based authorization.

    The service accepts both ORM ``User`` objects and lightweight principals
    used by application boundaries/tests. Authorization never assumes that a
    principal exposes every ORM property.
    """

    @staticmethod
    def _role_name(user: Any) -> Optional[str]:
        role = getattr(user, "role", None)
        return getattr(role, "name", None) if role is not None else None

    @staticmethod
    def _is_active(user: Any) -> bool:
        # Lightweight principals historically omit lifecycle state and are
        # treated as active. Real User objects always persist is_active.
        return bool(getattr(user, "is_active", True))

    @staticmethod
    def _canonical_permission_name(value: str) -> str:
        return LEGACY_CAPABILITY_ALIASES.get(value, value)

    @classmethod
    def _direct_permission_names(cls, user: Any) -> set[str]:
        permissions = getattr(user, "permissions", None)
        if permissions is None or callable(permissions):
            return set()
        try:
            return {
                cls._canonical_permission_name(str(value))
                for value in permissions
            }
        except TypeError:
            return set()

    @classmethod
    def _has_direct_permission(cls, user: Any, capability: str) -> bool:
        checker = getattr(user, "has_permission", None)
        if callable(checker) and checker(capability):
            return True
        return capability in cls._direct_permission_names(user)

    @classmethod
    def _grants(cls, user: Any, capability: Capability) -> bool:
        role_name = cls._role_name(user)

        # MANAGER retains the established employee-record management scope.
        # No other role receives an implicit capability grant.
        if capability.value in IMPLICIT_ROLE_CAPABILITIES.get(role_name, frozenset()):
            return True

        if cls._has_direct_permission(user, capability.value):
            return True

        # A broader write scope may imply the narrower self-profile mutation
        # scope. Read capabilities never imply write capabilities.
        for broader, implied in IMPLIED_CAPABILITIES.items():
            if capability.value in implied and cls._has_direct_permission(user, broader):
                return True

        return False

    @classmethod
    def decide(
        cls,
        user: Any,
        capability: Capability | str,
        context: Optional[AuthorizationContext] = None,
    ) -> AuthorizationDecision:
        if user is None or not cls._is_active(user) or cls._role_name(user) is None:
            return AuthorizationDecision.DENY

        canonical = capability if isinstance(capability, Capability) else Capability.from_value(capability)

        # Admin-only operations are explicit policy boundaries. They are the
        # only capabilities whose grant is role-derived. Generic capabilities
        # require an explicit persisted grant (or the narrow Manager policy).
        if canonical.value in ADMIN_ONLY_CAPABILITIES:
            return (
                AuthorizationDecision.ALLOW
                if cls._role_name(user) == RoleDefinitions.ADMIN
                else AuthorizationDecision.DENY
            )

        return AuthorizationDecision.ALLOW if cls._grants(user, canonical) else AuthorizationDecision.DENY

    @classmethod
    def allows(
        cls,
        user: Any,
        capability: Capability | str,
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return cls.decide(user, capability, context) is AuthorizationDecision.ALLOW

    @classmethod
    def require(
        cls,
        user: Any,
        capability: Capability | str,
        context: Optional[AuthorizationContext] = None,
    ) -> None:
        if not cls.allows(user, capability, context):
            canonical = capability if isinstance(capability, Capability) else Capability.from_value(capability)
            from centermanager.services.permission_service import PermissionDeniedError
            raise PermissionDeniedError(f"Capability '{canonical.value}' is required.")

    @classmethod
    def allows_any(
        cls,
        user: Any,
        capabilities: Iterable[Capability | str],
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return any(cls.allows(user, capability, context) for capability in capabilities)

    @classmethod
    def allows_all(
        cls,
        user: Any,
        capabilities: Iterable[Capability | str],
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return all(cls.allows(user, capability, context) for capability in capabilities)
