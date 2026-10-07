# -*- coding: utf-8 -*-
"""Canonical actor attribution for human-facing timeline/history projections."""
from __future__ import annotations

from typing import Optional

from centermanager.core.current_user import get_current_user


SYSTEM_ACTOR = "system"


def resolve_timeline_actor(explicit_actor: Optional[str] = None) -> str:
    """Return an explicit actor, current authenticated username, or system.

    Explicit values are authoritative so background/system handlers can pass
    "system" without being accidentally attributed to the logged-in user.
    """
    if explicit_actor is not None:
        value = str(explicit_actor).strip()
        if value:
            return value

    user = get_current_user()
    username = getattr(user, "username", None) if user is not None else None
    if username:
        return str(username)

    return SYSTEM_ACTOR
