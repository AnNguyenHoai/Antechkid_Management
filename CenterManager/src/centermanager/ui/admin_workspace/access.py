# -*- coding: utf-8 -*-
"""Safe Admin workspace access helpers.

Admin pages may be created during bootstrap before CollaborationManager is fully
initialized. UI state checks must therefore never call ensure_write() directly.
"""

from typing import Optional


def can_write(collaboration_manager) -> bool:
    """Return whether this client currently owns WRITE mode, without raising."""
    if collaboration_manager is None:
        return False
    try:
        if not collaboration_manager.is_initialized():
            return False
        return bool(collaboration_manager.is_writing())
    except Exception:
        return False


def notify(notification_service, message: str, severity: str = "info") -> None:
    """Best-effort notification safe for pages created without a service."""
    if notification_service is not None:
        notification_service.notify(message, severity)
