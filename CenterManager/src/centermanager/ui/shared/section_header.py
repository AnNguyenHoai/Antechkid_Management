# -*- coding: utf-8 -*-
"""Shared section heading with optional subtitle and trailing action."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from centermanager.ui.design_system.tokens import (
    COLORS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    SPACING,
    TYPOGRAPHY,
)


class SectionHeader(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._setup_ui(title, subtitle, action_text, action_callback)

    def _setup_ui(
        self,
        title: str,
        subtitle: Optional[str],
        action_text: Optional[str],
        action_callback: Optional[Callable[[], None]],
    ) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, SPACING["xs"])
        root.setSpacing(SPACING["sm"])

        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("SharedSectionTitle")
        copy.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle or "", self)
        self.subtitle_label.setObjectName("SharedSectionSubtitle")
        self.subtitle_label.setVisible(bool(subtitle))
        self.subtitle_label.setWordWrap(True)
        copy.addWidget(self.subtitle_label)
        root.addLayout(copy)
        root.addStretch()

        self.action_button: Optional[QPushButton] = None
        if action_text:
            self.action_button = QPushButton(action_text, self)
            self.action_button.setObjectName("SharedSectionAction")
            self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
            if action_callback is not None:
                self.action_button.clicked.connect(action_callback)
            root.addWidget(
                self.action_button,
                alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            )

        self.setStyleSheet(
            f"""
            QLabel#SharedSectionTitle {{
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['section_title']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#SharedSectionSubtitle {{
                color: {COLORS['text_muted']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            QPushButton#SharedSectionAction {{
                min-height: 28px;
                padding: 0 {SPACING['sm']}px;
                color: {COLORS['action_primary']};
                background: transparent;
                border: none;
                border-radius: {SPACING['xs']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QPushButton#SharedSectionAction:hover {{
                background: {COLORS['blue_50']};
                color: {COLORS['action_primary_hover']};
            }}
            QPushButton#SharedSectionAction:focus {{
                border: 2px solid {COLORS['focus_ring']};
            }}
            """
        )


__all__ = ["SectionHeader"]
