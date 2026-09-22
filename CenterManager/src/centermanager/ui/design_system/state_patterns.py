# -*- coding: utf-8 -*-
"""Product-level content-state patterns for Design System V2.

UI-PROD-07 does not replace the foundation state primitives. It gives common
product situations stable copy and semantics so workspaces do not invent
different empty/search/permission states during UI-PROD-08 migration.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QWidget

from .foundation import EmptyState, StateView
from .foundation import BadgeTone


class EmptySearchState(EmptyState):
    """Canonical state when a search/filter combination returns no results."""

    def __init__(
        self,
        *,
        query: str = "",
        clear_text: Optional[str] = "Clear search",
        clear_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        query = query.strip()
        description = (
            f'No results match "{query}". Try another keyword or clear the filters.'
            if query
            else "No results match the current search or filters."
        )
        super().__init__(
            icon="⌕",
            title="No results found",
            description=description,
            action_text=clear_text,
            action_callback=clear_callback,
            parent=parent,
        )


class PermissionState(StateView):
    """Canonical non-error state for content the current user cannot access."""

    def __init__(
        self,
        *,
        title: str = "You don't have access",
        description: str = (
            "Your current role does not allow this action or content. "
            "Contact an administrator if you need access."
        ),
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title,
            description,
            tone=BadgeTone.WARNING,
            symbol="!",
            action_text=action_text,
            action_callback=action_callback,
            parent=parent,
        )


__all__ = ["EmptySearchState", "PermissionState"]
