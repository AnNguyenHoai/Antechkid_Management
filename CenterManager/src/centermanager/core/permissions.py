# -*- coding: utf-8 -*-
"""Backward-compatible permission API backed by the canonical capability registry."""
from typing import Optional

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user


# Compatibility alias: new code should import Capability directly.
Permission = Capability


def has_permission(permission: Capability, user=None) -> bool:
    """Check a canonical capability for a user."""
    from centermanager.services.permission_service import PermissionService
    from centermanager.database.engine import create_production_engine
    from sqlalchemy.orm import sessionmaker

    if user is None:
        user = get_current_user()
    if user is None:
        return False

    engine = create_production_engine()
    session_factory = sessionmaker(bind=engine)
    service = PermissionService(session_factory)
    return service.has_permission(permission.value, user)


def require_permission(permission: Capability, user=None) -> None:
    """Require a canonical capability or raise ``PermissionDeniedError``."""
    if not has_permission(permission, user):
        from centermanager.services.permission_service import PermissionDeniedError
        raise PermissionDeniedError(f"Capability '{permission.value}' is required.")


# Legacy alias kept for compatibility with older callers.
def has_permission_legacy(permission: Capability, user=None) -> bool:
    return has_permission(permission, user)
