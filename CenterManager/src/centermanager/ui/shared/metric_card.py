# -*- coding: utf-8 -*-
"""
MetricCard - Reusable card for displaying a single metric.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, SPACING, BORDER_RADIUS


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
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Tăng 30%: từ 104-124 lên 135-161
        self.setMinimumHeight(135)
        self.setMaximumHeight(161)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['md'], SPACING['sm']+2, SPACING['md'], SPACING['sm']+2)
        layout.setSpacing(SPACING['xs'])

        # Top: Icon + Label
        top_layout = QHBoxLayout()
        top_layout.setSpacing(SPACING['xs'])
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 16px;")  # Giảm từ 18px
        top_layout.addWidget(icon_label)
        
        label_label = QLabel(label)
        label_label.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_muted']};
            font-weight: 500;
            letter-spacing: 0.3px;
            text-transform: uppercase;
        """)  # Giảm từ 12px xuống 10px (≈30%)
        top_layout.addWidget(label_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Value - giảm từ 28px xuống 20px (≈30%)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {COLORS['text_primary']};
            line-height: 1.2;
        """)
        layout.addWidget(self.value_label)

        if sub_value:
            sub_label = QLabel(sub_value)
            sub_label.setStyleSheet(f"""
                font-size: 10px;
                color: {COLORS['text_muted']};
            """)  # Giảm từ 12px xuống 10px
            layout.addWidget(sub_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)