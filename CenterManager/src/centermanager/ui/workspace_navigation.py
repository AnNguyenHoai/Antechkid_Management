# -*- coding: utf-8 -*-
"""WorkspaceNavigation - production sidebar navigation for a workspace."""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    CONTROL_SIZES,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class NavItem(QPushButton):
    """Compact text-first sidebar item with semantic selected state."""

    clicked_signal = Signal(str)

    def __init__(
        self,
        page_id: str,
        icon: str,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(label, parent)
        self._page_id = page_id
        self._icon = icon  # Kept for API compatibility; shell V2 is text-first.
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(self.text())
        self.setFixedHeight(CONTROL_SIZES["lg"]["height"])
        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                padding: 0 {SPACING['md']}px;
                border: none;
                border-left: {COMPONENT_METRICS['nav_indicator_width']}px solid transparent;
                border-radius: {RADIUS['md']}px;
                background: transparent;
                color: {COLORS['text_secondary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
                color: {COLORS['text_primary']};
            }}
            QPushButton:checked {{
                background: {COLORS['blue_50']};
                color: {COLORS['action_primary_hover']};
                border-left-color: {COLORS['action_primary']};
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QPushButton:focus {{
                border-color: {COLORS['focus_ring']};
            }}
            """
        )
        self.clicked.connect(lambda: self.clicked_signal.emit(self._page_id))


class WorkspaceNavigation(QWidget):
    """Shared production sidebar used by all workspaces."""

    page_selected = Signal(str)

    def __init__(
        self,
        workspace_name: str,
        pages: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pages = pages
        self._workspace_name = workspace_name
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("WorkspaceSidebar")
        self.setFixedWidth(COMPONENT_METRICS["workspace_sidebar_width"])
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            f"""
            QWidget#WorkspaceSidebar {{
                background: {COLORS['surface_page']};
                border: none;
                border-right: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("WorkspaceSidebarHeader")
        header.setFixedHeight(COMPONENT_METRICS["workspace_sidebar_header_height"])
        header.setStyleSheet(
            f"""
            QFrame#WorkspaceSidebarHeader {{
                background: {COLORS['surface_page']};
                border: none;
                border-bottom: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_subtle']};
            }}
            """
        )
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        header_layout.setSpacing(SPACING["xs"])

        eyebrow = QLabel("WORKSPACE")
        eyebrow.setStyleSheet(
            f"color: {COLORS['action_accent']}; font-family: {FONT_FAMILY}; "
            f"font-size: {TYPOGRAPHY['badge']}px; font-weight: {FONT_WEIGHTS['bold']}; letter-spacing: 0.6px;"
        )
        header_layout.addWidget(eyebrow)

        ws_label = QLabel(self._workspace_name.replace(" Workspace", ""))
        ws_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-family: {FONT_FAMILY}; "
            f"font-size: {TYPOGRAPHY['card_title']}px; font-weight: {FONT_WEIGHTS['semibold']};"
        )
        header_layout.addWidget(ws_label)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SPACING["sm"], SPACING["md"], SPACING["sm"], SPACING["md"])
        container_layout.setSpacing(SPACING["xs"])

        self._buttons: List[NavItem] = []
        for page in self._pages:
            button = NavItem(page["id"], page.get("icon", ""), page["label"])
            button.clicked_signal.connect(self._on_page_clicked)
            container_layout.addWidget(button)
            self._buttons.append(button)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_page_clicked(self, page_id: str) -> None:
        self.page_selected.emit(page_id)

    def set_active_page(self, page_id: str) -> None:
        for button in self._buttons:
            if button._page_id == page_id:
                button.setChecked(True)
                return


__all__ = ["NavItem", "WorkspaceNavigation"]
