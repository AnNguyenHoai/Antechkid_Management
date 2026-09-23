# -*- coding: utf-8 -*-
"""WorkspaceHeader - production page header and breadcrumb context."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from centermanager.ui.application_shell import Breadcrumbs
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    SPACING,
    TYPOGRAPHY,
)


class WorkspaceHeader(QWidget):
    """Shared page header for all workspace shells.

    Existing ``set_context`` and ``home_btn`` contracts are preserved so
    workspace navigation logic can migrate without behavioural changes.
    UI-PROD-09 lets the header grow with desktop typography instead of clipping
    it into a fixed-height prototype frame.
    """

    back_home_clicked = Signal()

    def __init__(
        self,
        workspace_name: str,
        current_page_label: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_name = workspace_name
        self._current_page = current_page_label
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("WorkspacePageHeader")
        self.setMinimumHeight(COMPONENT_METRICS["page_header_height"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(
            f"""
            QWidget#WorkspacePageHeader {{
                background: {COLORS['surface_page']};
                border: none;
                border-bottom: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["sm"], SPACING["lg"], SPACING["sm"])
        layout.setSpacing(SPACING["xs"])

        self.breadcrumbs = Breadcrumbs(self._workspace_name, self._current_page, self)
        self.breadcrumbs.home_clicked.connect(self.back_home_clicked.emit)
        self.home_btn = self.breadcrumbs.home_button
        layout.addWidget(self.breadcrumbs)

        self.page_title_label = QLabel(self._current_page or self._workspace_name, self)
        self.page_title_label.setAccessibleName("Current page")
        self.page_title_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-family: {FONT_FAMILY}; "
            f"font-size: {TYPOGRAPHY['page_title']}px; font-weight: {FONT_WEIGHTS['semibold']}; border: none;"
        )
        layout.addWidget(self.page_title_label)

        # Legacy inspection-only alias; intentionally not part of the visible layout.
        self.context_label = QLabel(f"{self._workspace_name} / {self._current_page}", self)
        self.context_label.setVisible(False)

    def set_context(self, workspace_name: str, page_label: str) -> None:
        self._workspace_name = workspace_name
        self._current_page = page_label
        self.breadcrumbs.set_path(workspace_name, page_label)
        self.page_title_label.setText(page_label or workspace_name)
        self.context_label.setText(f"{workspace_name} / {page_label}")


__all__ = ["WorkspaceHeader"]
