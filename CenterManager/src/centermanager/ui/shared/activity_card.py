# -*- coding: utf-8 -*-
"""Shared activity row with stable typography and timestamp hierarchy."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from centermanager.ui.design_system.tokens import (
    COLORS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class ActivityCard(QFrame):
    def __init__(
        self,
        icon: str,
        title: str,
        subtitle: str,
        time: datetime,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, title, subtitle, time)

    def _setup_ui(self, icon: str, title: str, subtitle: str, time: datetime) -> None:
        self.setObjectName("SharedActivityCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["sm"], SPACING["sm"], SPACING["sm"], SPACING["sm"])
        layout.setSpacing(SPACING["md"])

        icon_label = QLabel(icon or "•", self)
        icon_label.setObjectName("ActivityIconTile")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(34, 34)
        layout.addWidget(icon_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(1)
        title_label = QLabel(title, self)
        title_label.setObjectName("ActivityTitle")
        title_label.setWordWrap(True)
        content_layout.addWidget(title_label)

        sub_label = QLabel(subtitle, self)
        sub_label.setObjectName("ActivitySubtitle")
        sub_label.setWordWrap(True)
        content_layout.addWidget(sub_label)
        layout.addLayout(content_layout, 1)

        time_label = QLabel(self._format_time(time), self)
        time_label.setObjectName("ActivityTime")
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(time_label)

        self.setStyleSheet(
            f"""
            QFrame#SharedActivityCard {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {COLORS['border_subtle']};
                border-radius: {RADIUS['sm']}px;
            }}
            QFrame#SharedActivityCard:hover {{
                background: {COLORS['surface_hover']};
            }}
            QLabel#ActivityIconTile {{
                background: {COLORS['blue_50']};
                color: {COLORS['action_primary']};
                border: none;
                border-radius: {RADIUS['md']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['icon_small']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#ActivityTitle {{
                color: {COLORS['text_primary']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#ActivitySubtitle {{
                color: {COLORS['text_muted']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['caption']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            QLabel#ActivityTime {{
                color: {COLORS['text_muted']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['caption']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            """
        )

    @staticmethod
    def _format_time(dt: datetime) -> str:
        now = datetime.now()
        if dt.date() == now.date():
            return f"Today {dt.strftime('%H:%M')}"
        if (now.date() - dt.date()).days == 1:
            return f"Yesterday {dt.strftime('%H:%M')}"
        return dt.strftime("%d/%m/%Y %H:%M")


__all__ = ["ActivityCard"]
