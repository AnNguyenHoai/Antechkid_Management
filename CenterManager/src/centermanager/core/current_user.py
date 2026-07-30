# -*- coding: utf-8 -*-
"""
Current user context - thread-local storage for the currently authenticated user.
"""
import threading
from typing import Optional

from centermanager.models.user import User

# Thread-local storage for current user
_thread_local = threading.local()


def get_current_user() -> Optional[User]:
    """Get the current user from thread-local storage."""
    return getattr(_thread_local, 'current_user', None)


def set_current_user(user: Optional[User]) -> None:
    """Set the current user in thread-local storage."""
    _thread_local.current_user = user


def clear_current_user() -> None:
    """Clear the current user from thread-local storage."""
    if hasattr(_thread_local, 'current_user'):
        del _thread_local.current_user


class CurrentUserContext:
    """
    Context manager for temporarily setting the current user.

    Usage:
        with CurrentUserContext(user):
            # User is set for this block
            ...
    """
    def __init__(self, user: Optional[User]):
        self._user = user
        self._previous_user = None

    def __enter__(self):
        self._previous_user = get_current_user()
        set_current_user(self._user)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        set_current_user(self._previous_user)