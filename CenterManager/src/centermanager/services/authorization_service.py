# -*- coding: utf-8 -*-
"""Centralized authorization decisions for application capabilities."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Iterable

from centermanager.core.capabilities import Capability
from centermanager.models.user import User


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class AuthorizationContext:
    """Optional context carried with a capability decision.

    Resource and edit-session checks remain separate domain/application
    invariants. This object only describes the authorization request and does
    not grant permissions by itself.
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
        # Deliberately no role-name bypass: even ADMIN is authorized through
        # the explicit capability grants assigned to that role.
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
