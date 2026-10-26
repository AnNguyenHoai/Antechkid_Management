# -*- coding: utf-8 -*-
"""Shared attention banner for actionable warnings and status follow-up."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

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


_SEVERITY = {
    "warning": (COLORS["state_warning_bg"], COLORS["state_warning"]),
    "critical": (COLORS["state_danger_bg"], COLORS["state_danger"]),
    "info": (COLORS["state_info_bg"], COLORS["state_info"]),
    "success": (COLORS["state_success_bg"], COLORS["state_success"]),
}


class WarningBanner(QFrame):
    clicked = Signal(object)

    def __init__(
        self,
        message: str,
        icon: str = "!",
        severity: str = "warning",
        action_text: Optional[str] = "Open →",
        action_data: Optional[object] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._action_data = action_data
        self._severity = severity if severity in _SEVERITY else "info"
        self._setup_ui(message, icon, action_text)

    def _setup_ui(self, message: str, icon: str, action_text: Optional[str]) -> None:
        bg, fg = _SEVERITY[self._severity]
        self.setObjectName("SharedWarningBanner")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        layout.setSpacing(SPACING["md"])

        if AppIcon.supports(icon):
            icon_label = AppIcon(
                icon,
                size=18,
                color=COLORS["text_inverse"],
                tile_color=fg,
                tile_size=36,
                parent=self,
            )
        else:
            icon_label = QLabel(icon or "!", self)
            icon_label.setObjectName("WarningIconTile")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(36, 36)
        layout.addWidget(icon_label)

        self.message_label = QLabel(message, self)
        self.message_label.setObjectName("WarningMessage")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)

        self.action_button: Optional[QPushButton] = None
        if action_text:
            self.action_button = QPushButton(action_text, self)
            self.action_button.setObjectName("WarningAction")
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_button.clicked.connect(self._on_click)
            layout.addWidget(self.action_button)

        self.setStyleSheet(
            f"""
            QFrame#SharedWarningBanner {{
                background: {bg};
                border: {COMPONENT_METRICS['border_width']}px solid {fg};
                border-radius: {RADIUS['lg']}px;
            }}
            QFrame#SharedWarningBanner:hover {{
                border-color: {fg};
            }}
            QFrame#SharedWarningBanner:focus {{
                border: 2px solid {COLORS['focus_ring']};
            }}
            QLabel#WarningIconTile {{
                background: {fg};
                color: {COLORS['text_inverse']};
                border: none;
                border-radius: {RADIUS['md']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['icon_small']}px;
                font-weight: {FONT_WEIGHTS['bold']};
            }}
            QLabel#WarningMessage {{
                color: {COLORS['text_primary']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['medium']};
            }}
            QPushButton#WarningAction {{
                min-height: 30px;
                padding: 0 {SPACING['sm']}px;
                color: {COLORS['action_primary']};
                background: transparent;
                border: none;
                border-radius: {RADIUS['sm']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QPushButton#WarningAction:hover {{
                background: {COLORS['surface_card']};
                color: {COLORS['action_primary_hover']};
            }}
            """
        )

    def _on_click(self) -> None:
        self.clicked.emit(self._action_data)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._on_click()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
            event.accept()
            return
        super().mousePressEvent(event)


__all__ = ["WarningBanner"]
