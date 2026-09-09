# -*- coding: utf-8 -*-
"""Centralized authorization decisions for application capabilities."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Iterable

from centermanager.core.capabilities import Capability, ADMIN_ONLY_CAPABILITIES
from centermanager.models.role import RoleDefinitions
from centermanager.models.user import User


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
    """Single entry point for capability-based authorization."""

    @staticmethod
    def decide(
        user: Optional[User],
        capability: Capability | str,
        context: Optional[AuthorizationContext] = None,
    ) -> AuthorizationDecision:
        if user is None or not user.is_active or user.role is None:
            return AuthorizationDecision.DENY

        canonical = capability if isinstance(capability, Capability) else Capability.from_value(capability)

        # Administrative operations have an explicit, centralized policy.
        # They are not generic "admin gets everything" access and are never
        # inferred from WRITE mode or a UI state.
        if canonical.value in ADMIN_ONLY_CAPABILITIES:
            return (
                AuthorizationDecision.ALLOW
                if user.role.name == RoleDefinitions.ADMIN
                else AuthorizationDecision.DENY
            )

        return (
            AuthorizationDecision.ALLOW
            if user.has_permission(canonical.value)
            else AuthorizationDecision.DENY
        )

    @classmethod
    def allows(
        cls,
        user: Optional[User],
        capability: Capability | str,
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return cls.decide(user, capability, context) is AuthorizationDecision.ALLOW

    @classmethod
    def require(
        cls,
        user: Optional[User],
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
        user: Optional[User],
        capabilities: Iterable[Capability | str],
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return any(cls.allows(user, capability, context) for capability in capabilities)

    @classmethod
    def allows_all(
        cls,
        user: Optional[User],
        capabilities: Iterable[Capability | str],
        context: Optional[AuthorizationContext] = None,
    ) -> bool:
        return all(cls.allows(user, capability, context) for capability in capabilities)
