# -*- coding: utf-8 -*-
"""Compatibility wrappers for Design System V2 loading components."""
from typing import Optional

from PySide6.QtWidgets import QWidget

from centermanager.ui.design_system.foundation import LoadingState, Skeleton


class LoadingSkeleton(Skeleton):
    """Backward-compatible name for the canonical skeleton primitive."""


class LoadingWidget(LoadingState):
    """Legacy loading widget API backed by the canonical loading state.

    Existing call sites commonly pass ``count`` to request skeleton rows.
    """

    def __init__(
        self,
        count: int = 5,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(skeleton_rows=max(0, count), parent=parent)


__all__ = ["LoadingWidget", "LoadingSkeleton"]
