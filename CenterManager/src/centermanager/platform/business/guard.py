# -*- coding: utf-8 -*-
"""Read/Write guards for business operations."""

import logging
from functools import wraps
from typing import Callable, Optional

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import CollaborationManager
from centermanager.core.current_user import get_current_user
from centermanager.services.permission_service import PermissionDeniedError

logger = logging.getLogger(__name__)


class WriteGuard:
    """
    Guard for write operations.
    Checks collaboration state before allowing writes.
    """

    def __init__(self, collaboration_manager: CollaborationManager):
        self._collab_manager = collaboration_manager

    def can_write(self) -> bool:
        """Check if write is allowed."""
        if not self._collab_manager.is_initialized():
            return False
        return self._collab_manager.is_writing()

    def require_write(self) -> None:
        """Require write permission. Raises PermissionDeniedError if not allowed."""
        if not self.can_write():
            raise PermissionDeniedError("Write access not granted. Request write mode first.")

    def require_write_for_method(self, method: Callable) -> Callable:
        """Decorator to require write access for a method."""
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            self.require_write()
            return method(self, *args, **kwargs)
        return wrapper


class ReadGuard:
    """
    Guard for read operations.
    Checks that platform is ready for reads.
    """

    def __init__(self, context: PlatformContext):
        self._context = context

    def can_read(self) -> bool:
        """Check if read is allowed."""
        return self._context.is_ready()

    def require_read(self) -> None:
        """Require read permission."""
        if not self.can_read():
            raise RuntimeError("Platform not ready for read operations")


class PermissionGuard:
    """
    Combined permission and write guard.
    Checks both permission and collaboration state.
    """

    def __init__(self, collaboration_manager: CollaborationManager, context: PlatformContext):
        self._write_guard = WriteGuard(collaboration_manager)
        self._read_guard = ReadGuard(context)

    def can_write(self) -> bool:
        return self._write_guard.can_write()

    def can_read(self) -> bool:
        return self._read_guard.can_read()

    def require_write(self, permission: Optional[str] = None) -> None:
        """Require write permission and optional business permission."""
        self._write_guard.require_write()
        if permission:
            self._require_permission(permission)

    def require_read(self, permission: Optional[str] = None) -> None:
        """Require read permission and optional business permission."""
        self._read_guard.require_read()
        if permission:
            self._require_permission(permission)

    def _require_permission(self, permission: str) -> None:
        """Check business permission."""
        user = get_current_user()
        if user and user.has_permission(permission):
            return
        if user and user.is_admin:
            return
        raise PermissionDeniedError(f"Permission '{permission}' required")