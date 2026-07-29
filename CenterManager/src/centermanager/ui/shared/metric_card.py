# -*- coding: utf-8 -*-
"""
MetricCard - Reusable card for displaying a single metric.
Redesigned: Value as primary, label as secondary.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class MetricCard(QFrame):
    def __init__(
        self,
        icon: str,
        label: str,
        value: str,
        sub_value: Optional[str] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, label, value, sub_value)

    def _setup_ui(self, icon: str, label: str, value: str, sub_value: Optional[str]) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border-radius: {BORDER_RADIUS['md']}px;
                border: 1px solid {COLORS['border_light']};
                padding: {SPACING['md']}px {SPACING['lg']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(72)
        self.setMaximumHeight(88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['md'], SPACING['sm'], SPACING['md'], SPACING['sm'])
        layout.setSpacing(SPACING['xs'])

        # Top: Icon + Label (small, muted)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(SPACING['xs'])
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        top_layout.addWidget(icon_label)
        
        label_label = QLabel(label)
        label_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['text_muted']};
            font-weight: 500;
            letter-spacing: 0.3px;
            text-transform: uppercase;
        """)
        top_layout.addWidget(label_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Value (large, bold) - primary visual
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['stat_value_large']}px;
            font-weight: 700;
            color: {COLORS['text_primary']};
            line-height: 1.2;
        """)
        layout.addWidget(self.value_label)

        if sub_value:
            sub_label = QLabel(sub_value)
            sub_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['caption']}px;
                color: {COLORS['text_muted']};
            """)
            layout.addWidget(sub_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)