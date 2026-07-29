# -*- coding: utf-8 -*-
"""
SummaryCard - mini card for summary widget.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class SummaryCard(QFrame):
    """Mini card displaying one summary item."""
    
    def __init__(
        self,
        icon: str,
        title: str,
        value: str,
        sub_value: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {COLORS['border_light']};
                border-radius: {BORDER_RADIUS['md']}px;
                background: {COLORS['surface']};
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(80)  # tăng lên 80 để đủ chỗ

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['xs'])

        # Top row: Icon + Title
        top_layout = QHBoxLayout()
        top_layout.setSpacing(SPACING['xs'])
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_small']}px;")
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['text_muted']};
            font-weight: 500;
            letter-spacing: 0.2px;
        """)
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Value
        value_label = QLabel(value or "-")
        value_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['stat_value']}px;
            font-weight: 700;
            color: {COLORS['text_primary']};
            line-height: 1.2;
        """)
        value_label.setWordWrap(False)
        layout.addWidget(value_label)

        if sub_value:
            sub_label = QLabel(sub_value)
            sub_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['caption']}px;
                color: {COLORS['text_muted']};
            """)
            layout.addWidget(sub_label)