# -*- coding: utf-8 -*-
"""Global application navigation used by the CenterManager shell."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class GlobalNavItem(QPushButton):
    selected = Signal(str)

    def __init__(self, item_id: str, icon: str, label: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(f"{icon}  {label}", parent)
        self.item_id = item_id
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setAccessibleName(label)
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
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
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
                border: 2px solid {COLORS['focus_ring']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_disabled']};
            }}
            """
        )
        self.clicked.connect(lambda: self.selected.emit(self.item_id))


class GlobalSidebar(QFrame):
    """Persistent level-1 navigation. Workspace-local navigation remains unchanged."""

    navigation_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlobalSidebar")
        self.setFixedWidth(182)
        self._items: dict[str, GlobalNavItem] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(
            f"""
            QFrame#GlobalSidebar {{
                background: {COLORS['surface_page']};
                border: none;
                border-right: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
            }}
            QLabel#GlobalNavSection {{
                color: {COLORS['text_muted']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['badge']}px;
                font-weight: {FONT_WEIGHTS['bold']};
                letter-spacing: 0.7px;
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING["sm"], SPACING["md"], SPACING["sm"], SPACING["md"])
        root.setSpacing(SPACING["xs"])

        self._add_item(root, "home", "⌂", "Center overview")

        root.addSpacing(SPACING["lg"])
        self._add_section(root, "WORKSPACE")
        self._add_item(root, "student", "●", "Student Workspace")
        self._add_item(root, "teacher", "✓", "Teacher Workspace")
        self._add_item(root, "class", "◆", "Class Workspace")
        self._add_item(root, "finance", "▣", "Finance Workspace")
        self._add_item(root, "employee", "▤", "Employee Workspace")

        root.addSpacing(SPACING["lg"])
        self._add_section(root, "GENERAL")
        self._add_item(root, "settings", "⚙", "Settings")
        self._add_item(root, "reports", "▥", "Reports")

        root.addStretch()
        self.set_active("home")

    def _add_section(self, layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text, self)
        label.setObjectName("GlobalNavSection")
        label.setContentsMargins(SPACING["xs"], 0, 0, 0)
        layout.addWidget(label)

    def _add_item(self, layout: QVBoxLayout, item_id: str, icon: str, label: str) -> None:
        item = GlobalNavItem(item_id, icon, label, self)
        item.selected.connect(self.navigation_requested.emit)
        layout.addWidget(item)
        self._items[item_id] = item

    def set_active(self, item_id: str) -> None:
        item = self._items.get(item_id)
        if item is not None:
            item.setChecked(True)

    def set_item_visible(self, item_id: str, visible: bool) -> None:
        item = self._items.get(item_id)
        if item is not None:
            item.setVisible(bool(visible))


__all__ = ["GlobalSidebar", "GlobalNavItem"]
