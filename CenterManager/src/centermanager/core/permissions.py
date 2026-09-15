# -*- coding: utf-8 -*-
"""Backward-compatible permission API backed by the canonical capability registry."""

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user


# Compatibility alias: new code should import Capability directly.
Permission = Capability


def _canonical(permission: Capability | str) -> Capability:
    return permission if isinstance(permission, Capability) else Capability.from_value(permission)


def has_permission(permission: Capability | str, user=None) -> bool:
    """Check a canonical capability for a user."""
    from centermanager.services.permission_service import PermissionService
    from centermanager.database.engine import create_production_engine
    from sqlalchemy.orm import sessionmaker

    if user is None:
        user = get_current_user()
    if user is None:
        return False

    capability = _canonical(permission)
    engine = create_production_engine()
    session_factory = sessionmaker(bind=engine)
    service = PermissionService(session_factory)
    return service.has_permission(capability.value, user)


def require_permission(permission: Capability | str, user=None) -> None:
    """Require a canonical capability or raise ``PermissionDeniedError``."""
    capability = _canonical(permission)
    if not has_permission(capability, user):
        from centermanager.services.permission_service import PermissionDeniedError
        raise PermissionDeniedError(f"Capability '{capability.value}' is required.")


# Legacy alias kept for compatibility with older callers.
def has_permission_legacy(permission: Capability | str, user=None) -> bool:
    return has_permission(permission, user)
