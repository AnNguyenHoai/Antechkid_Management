# -*- coding: utf-8 -*-
"""
SummaryCard - mini card for summary widget.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy


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
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background: white;
                padding: 6px 10px;
            }
        """)
        # Fix: use QSizePolicy.Minimum constant
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(icon_label)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: #666; font-weight: 500;")
        layout.addWidget(title_label)

        # Value
        value_label = QLabel(value or "-")
        value_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #222;")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        # Sub value
        if sub_value:
            sub_label = QLabel(sub_value)
            sub_label.setStyleSheet("font-size: 11px; color: #888;")
            layout.addWidget(sub_label)

        layout.addStretch()