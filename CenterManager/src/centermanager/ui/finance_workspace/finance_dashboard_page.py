# -*- coding: utf-8 -*-
"""
FinanceDashboardPage - placeholder for Finance Dashboard.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class FinanceDashboardPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("💰")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
        layout.addWidget(icon)

        title = QLabel("Finance Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['page_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title)

        subtitle = QLabel("Coming soon in Sprint 2.3")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            color: {COLORS['muted']};
        """)
        layout.addWidget(subtitle)

        layout.addStretch()