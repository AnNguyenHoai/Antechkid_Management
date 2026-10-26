# -*- coding: utf-8 -*-
"""Reusable visual metric card used across workspace dashboards."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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


_TONES = {
    "primary": (COLORS["blue_50"], COLORS["action_primary"]),
    "success": (COLORS["state_success_bg"], COLORS["state_success"]),
    "warning": (COLORS["state_warning_bg"], COLORS["state_warning"]),
    "danger": (COLORS["state_danger_bg"], COLORS["state_danger"]),
    "info": (COLORS["state_info_bg"], COLORS["state_info"]),
    "neutral": (COLORS["gray_100"], COLORS["text_secondary"]),
}


class MetricCard(QFrame):
    """Compact KPI card with a consistent icon tile and information hierarchy."""

    def __init__(
        self,
        icon: str,
        label: str,
        value: str,
        sub_value: Optional[str] = None,
        parent: Optional[QWidget] = None,
        *,
        tone: str = "neutral",
        compact: bool = False,
    ) -> None:
        super().__init__(parent)
        self._tone = tone if tone in _TONES else "neutral"
        self._compact = bool(compact)
        self._setup_ui(icon, label, value, sub_value)

    def _setup_ui(self, icon: str, label: str, value: str, sub_value: Optional[str]) -> None:
        icon_bg, icon_fg = _TONES[self._tone]
        self.setObjectName("SharedMetricCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(84 if self._compact else 96)
        self.setMaximumHeight(112 if self._compact else 124)
        self.setStyleSheet(
            f"""
            QFrame#SharedMetricCard {{
                background: {COLORS['surface_card']};
                border: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']}px;
            }}
            QFrame#SharedMetricCard:hover {{
                border-color: {COLORS['border_strong']};
                background: {COLORS['surface_hover']};
            }}
            QLabel#MetricIconTile {{
                background: {icon_bg};
                color: {icon_fg};
                border: none;
                border-radius: {RADIUS['md']}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['icon']}px;
                font-weight: {FONT_WEIGHTS['bold']};
            }}
            QLabel#MetricLabel {{
                color: {COLORS['text_secondary']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
            }}
            QLabel#MetricValue {{
                color: {COLORS['text_primary']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['stat_value']}px;
                font-weight: {FONT_WEIGHTS['bold']};
            }}
            QLabel#MetricSubValue {{
                color: {COLORS['text_muted']};
                border: none;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['caption']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            """
        )

        root = QHBoxLayout(self)
        root.setContentsMargins(
            SPACING["md"],
            SPACING["sm"] if self._compact else SPACING["md"],
            SPACING["md"],
            SPACING["sm"] if self._compact else SPACING["md"],
        )
        root.setSpacing(SPACING["md"])

        icon_size = 34 if self._compact else 40
        if AppIcon.supports(icon):
            icon_label = AppIcon(
                icon,
                size=18 if self._compact else 20,
                color=icon_fg,
                tile_color=icon_bg,
                tile_size=icon_size,
                parent=self,
            )
        else:
            icon_label = QLabel(icon or "•", self)
            icon_label.setObjectName("MetricIconTile")
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setFixedSize(icon_size, icon_size)
        root.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(1)
        label_label = QLabel(label, self)
        label_label.setObjectName("MetricLabel")
        label_label.setWordWrap(True)
        copy.addWidget(label_label)

        self.value_label = QLabel(value, self)
        self.value_label.setObjectName("MetricValue")
        copy.addWidget(self.value_label)

        self.sub_value_label = QLabel(sub_value or "", self)
        self.sub_value_label.setObjectName("MetricSubValue")
        self.sub_value_label.setVisible(bool(sub_value))
        self.sub_value_label.setWordWrap(True)
        copy.addWidget(self.sub_value_label)
        copy.addStretch()
        root.addLayout(copy, 1)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_sub_value(self, value: Optional[str]) -> None:
        self.sub_value_label.setText(value or "")
        self.sub_value_label.setVisible(bool(value))


__all__ = ["MetricCard"]
