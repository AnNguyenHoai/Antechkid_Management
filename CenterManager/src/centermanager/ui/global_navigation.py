# -*- coding: utf-8 -*-
"""Global application navigation used by the CenterManager shell."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from centermanager.ui.app_icon import AppIcon
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

    def __init__(
        self,
        item_id: str,
        icon_name: str,
        label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.item_id = item_id
        self._label_text = label
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self.setAccessibleName(label)

        row = QHBoxLayout(self)
        row.setContentsMargins(SPACING["md"], 0, SPACING["md"], 0)
        row.setSpacing(SPACING["sm"])
        self.icon_widget = AppIcon(
            icon_name,
            size=17,
            color=COLORS["text_secondary"],
            tile_size=20,
            parent=self,
        )
        row.addWidget(self.icon_widget)
        self.label_widget = QLabel(label, self)
        self.label_widget.setObjectName("GlobalNavItemLabel")
        row.addWidget(self.label_widget, 1)

        self.setStyleSheet(
            f"""
            QPushButton {{
                text-align: left;
                border: none;
                border-left: {COMPONENT_METRICS['nav_indicator_width']}px solid transparent;
                border-radius: {RADIUS['md']}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
            }}
            QPushButton:checked {{
                background: {COLORS['blue_50']};
                border-left-color: {COLORS['action_primary']};
            }}
            QPushButton:focus {{
                border: 2px solid {COLORS['focus_ring']};
            }}
            QLabel#GlobalNavItemLabel {{
                color: {COLORS['text_secondary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
                background: transparent;
                border: none;
            }}
            QPushButton:checked QLabel#GlobalNavItemLabel {{
                color: {COLORS['action_primary_hover']};
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            """
        )
        self.toggled.connect(self._sync_visual_state)
        self.clicked.connect(lambda: self.selected.emit(self.item_id))
        self._sync_visual_state(False)

    def _sync_visual_state(self, checked: bool) -> None:
        self.icon_widget._color = (
            COLORS["action_primary"] if checked else COLORS["text_secondary"]
        )
        self.icon_widget._render()


class GlobalSidebar(QFrame):
    """Persistent level-1 navigation. Workspace-local navigation remains unchanged."""

    navigation_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("GlobalSidebar")
        self.setFixedWidth(204)
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

        self._add_item(root, "home", "home", "Center overview")

        root.addSpacing(SPACING["lg"])
        self._add_section(root, "WORKSPACE")
        self._add_item(root, "student", "student", "Student Workspace")
        self._add_item(root, "teacher", "teacher", "Teacher Workspace")
        self._add_item(root, "class", "class", "Class Workspace")
        self._add_item(root, "finance", "finance", "Finance Workspace")
        self._add_item(root, "employee", "employee", "Employee Workspace")

        root.addSpacing(SPACING["lg"])
        self._add_section(root, "GENERAL")
        self._add_item(root, "settings", "settings", "Settings")
        self._add_item(root, "reports", "reports", "Reports")

        root.addStretch()
        self.set_active("home")

    def _add_section(self, layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text, self)
        label.setObjectName("GlobalNavSection")
        label.setContentsMargins(SPACING["xs"], 0, 0, 0)
        layout.addWidget(label)

    def _add_item(self, layout: QVBoxLayout, item_id: str, icon_name: str, label: str) -> None:
        item = GlobalNavItem(item_id, icon_name, label, self)
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
