# -*- coding: utf-8 -*-
"""Shared entity header for workspace detail/profile pages."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

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


_STATUS_TONES = {
    "ACTIVE": (COLORS["state_success_bg"], COLORS["state_success"]),
    "INACTIVE": (COLORS["gray_100"], COLORS["text_secondary"]),
    "ARCHIVED": (COLORS["state_warning_bg"], COLORS["state_warning"]),
    "DELETED": (COLORS["state_danger_bg"], COLORS["state_danger"]),
    "VOIDED": (COLORS["state_danger_bg"], COLORS["state_danger"]),
    "PAID": (COLORS["state_success_bg"], COLORS["state_success"]),
}


class EntityHeader(QFrame):
    """Consistent identity header with icon, title, metadata, status and actions."""

    def __init__(
        self,
        *,
        icon: str,
        title: str = "",
        identifier: str = "",
        subtitle: str = "",
        status: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("SharedEntityHeader")
        self.setFrameShape(QFrame.Shape.NoFrame)

        root = QHBoxLayout(self)
        root.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        root.setSpacing(SPACING["md"])

        self.icon = AppIcon(
            icon,
            size=22,
            color=COLORS["action_primary"],
            tile_color=COLORS["blue_50"],
            tile_size=44,
            parent=self,
        )
        root.addWidget(self.icon, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("EntityHeaderTitle")
        self.title_label.setWordWrap(True)
        copy.addWidget(self.title_label)

        meta = QHBoxLayout()
        meta.setSpacing(SPACING["sm"])
        self.identifier_label = QLabel(identifier, self)
        self.identifier_label.setObjectName("EntityHeaderIdentifier")
        self.identifier_label.setVisible(bool(identifier))
        meta.addWidget(self.identifier_label)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("EntityHeaderStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setVisible(bool(status))
        meta.addWidget(self.status_label)
        meta.addStretch()
        copy.addLayout(meta)

        self.subtitle_label = QLabel(subtitle, self)
        self.subtitle_label.setObjectName("EntityHeaderSubtitle")
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setVisible(bool(subtitle))
        copy.addWidget(self.subtitle_label)
        root.addLayout(copy, 1)

        self.actions = QWidget(self)
        self.actions_layout = QHBoxLayout(self.actions)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(SPACING["sm"])
        root.addWidget(self.actions, alignment=Qt.AlignmentFlag.AlignTop)

        self.setStyleSheet(
            f"""
            QFrame#SharedEntityHeader {{
                background: {COLORS['surface_card']};
                border: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']}px;
            }}
            QLabel#EntityHeaderTitle {{
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['section_title']}px;
                font-weight: {FONT_WEIGHTS['bold']};
                border: none;
                background: transparent;
            }}
            QLabel#EntityHeaderIdentifier,
            QLabel#EntityHeaderSubtitle {{
                color: {COLORS['text_muted']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['regular']};
                border: none;
                background: transparent;
            }}
            QLabel#EntityHeaderStatus {{
                min-height: 22px;
                padding: 0 {SPACING['sm']}px;
                border-radius: {RADIUS['pill']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['badge']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            """
        )
        self.set_status(status)

    def add_action(self, widget: QWidget) -> QWidget:
        self.actions_layout.addWidget(widget)
        return widget

    def set_identity(
        self,
        *,
        title: Optional[str] = None,
        identifier: Optional[str] = None,
        subtitle: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        if title is not None:
            self.title_label.setText(title)
        if identifier is not None:
            self.identifier_label.setText(identifier)
            self.identifier_label.setVisible(bool(identifier))
        if subtitle is not None:
            self.subtitle_label.setText(subtitle)
            self.subtitle_label.setVisible(bool(subtitle))
        if status is not None:
            self.set_status(status)

    def set_status(self, status: str) -> None:
        text = (status or "").strip()
        self.status_label.setText(text.replace("_", " "))
        self.status_label.setVisible(bool(text))
        bg, fg = _STATUS_TONES.get(
            text.upper(),
            (COLORS["state_info_bg"], COLORS["state_info"]),
        )
        self.status_label.setStyleSheet(
            f"""
            QLabel#EntityHeaderStatus {{
                background: {bg};
                color: {fg};
                border: 1px solid {fg};
                border-radius: {RADIUS['pill']}px;
                padding: 0 {SPACING['sm']}px;
            }}
            """
        )


__all__ = ["EntityHeader"]
