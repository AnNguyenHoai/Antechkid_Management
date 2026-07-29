# -*- coding: utf-8 -*-
"""
SummaryCard - mini card for summary widget.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, SPACING, BORDER_RADIUS


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
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        # Tăng 30%: từ 104-130 lên 135-169
        self.setMinimumHeight(135)
        self.setMaximumHeight(169)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['md'], SPACING['sm']+2, SPACING['md'], SPACING['sm']+2)
        layout.setSpacing(SPACING['xs'])

        # Top: Icon + Title
        top_layout = QHBoxLayout()
        top_layout.setSpacing(SPACING['xs'])
        
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 14px;")  # Giảm từ 18px
        top_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_muted']};
            font-weight: 500;
            letter-spacing: 0.2px;
        """)  # Giảm từ 12px xuống 10px
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Value - giảm từ 24px xuống 17px (≈30%)
        value_label = QLabel(value or "-")
        value_label.setStyleSheet(f"""
            font-size: 17px;
            font-weight: 700;
            color: {COLORS['text_primary']};
            line-height: 1.2;
        """)
        value_label.setWordWrap(False)
        layout.addWidget(value_label)

        # Sub value
        if sub_value:
            sub_label = QLabel(sub_value)
            sub_label.setStyleSheet(f"""
                font-size: 10px;
                color: {COLORS['text_muted']};
            """)  # Giảm từ 12px xuống 10px
            layout.addWidget(sub_label)