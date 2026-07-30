# -*- coding: utf-8 -*-
"""
Permission Guard - middleware for checking permissions before executing operations.
"""
import logging
from functools import wraps
from typing import Optional, Callable, List, Type, Any

from centermanager.core.current_user import get_current_user
from centermanager.services.permission_service import PermissionDeniedError, PermissionService
from centermanager.models.user import User

logger = logging.getLogger(__name__)


class PermissionGuard:
    """
    Permission guard for protecting operations.

    Usage:
        # As a decorator for service methods
        @PermissionGuard.require("finance.view")
        def get_dashboard(self):
            ...

        # As a function call
        guard = PermissionGuard(session_factory)
        guard.check("finance.view")

        # For class methods
        class MyService:
            @PermissionGuard.require_permission("student.view")
            def list_students(self):
                ...
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._permission_service = PermissionService(session_factory)

    def check(self, permission_name: str, user: Optional[User] = None) -> bool:
        """
        Check a permission. Returns True if granted, False otherwise.
        """
        return self._permission_service.has_permission(permission_name, user)

    def require(self, permission_name: str, user: Optional[User] = None) -> None:
        """
        Require a permission. Raises PermissionDeniedError if not granted.
        """
        self._permission_service.require_permission(permission_name, user)

    def require_any(self, permission_names: List[str], user: Optional[User] = None) -> None:
        """
        Require any of the given permissions.
        """
        self._permission_service.require_any_permission(permission_names, user)

    def get_current_user(self) -> Optional[User]:
        """Get the current user."""
        return get_current_user()

    @classmethod
    def require_permission(cls, permission_name: str):
        """
        Decorator to require a permission for a method.

        Usage:
            @PermissionGuard.require_permission("finance.view")
            def my_method(self, *args, **kwargs):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                # Get session_factory from self if available
                session_factory = getattr(self, '_session_factory', None)
                if session_factory is None:
                    # Try to get from args or kwargs
                    session_factory = kwargs.get('session_factory')
                    if session_factory is None:
                        raise ValueError(
                            "Cannot find session_factory. "
                            "Make sure the class has _session_factory attribute "
                            "or pass session_factory as a keyword argument."
                        )

                guard = PermissionGuard(session_factory)
                guard.require(permission_name)
                return func(self, *args, **kwargs)
            return wrapper
        return decorator

    @classmethod
    def require_any_permission(cls, permission_names: List[str]):
        """
        Decorator to require any of the given permissions.
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(self, *args, **kwargs):
                session_factory = getattr(self, '_session_factory', None)
                if session_factory is None:
                    session_factory = kwargs.get('session_factory')
                    if session_factory is None:
                        raise ValueError("Cannot find session_factory")

                guard = PermissionGuard(session_factory)
                guard.require_any(permission_names)
                return func(self, *args, **kwargs)
            return wrapper
        return decorator


# Convenience functions
def require_permission(permission_name: str):
    """Alias for PermissionGuard.require_permission"""
    return PermissionGuard.require_permission(permission_name)


def require_any_permission(permission_names: List[str]):
    """Alias for PermissionGuard.require_any_permission"""
    return PermissionGuard.require_any_permission(permission_names)