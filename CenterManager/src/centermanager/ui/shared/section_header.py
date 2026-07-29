# -*- coding: utf-8 -*-
"""
SectionHeader - Header with title, optional subtitle, and optional action button.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class SectionHeader(QWidget):
    def __init__(
        self,
        title: str,
        subtitle: Optional[str] = None,
        action_text: Optional[str] = None,
        action_callback: Optional[callable] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(title, subtitle, action_text, action_callback)

    def _setup_ui(self, title: str, subtitle: Optional[str], action_text: Optional[str], action_callback: Optional[callable]) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, SPACING['sm'])
        layout.setSpacing(SPACING['sm'])

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['section_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body_small']}px;
                color: {COLORS['muted']};
            """)
            layout.addWidget(sub_label)

        layout.addStretch()

        if action_text and action_callback:
            btn = QPushButton(action_text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['primary']};
                    border: none;
                    font-size: {TYPOGRAPHY['body_small']}px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                }}
            """)
            btn.clicked.connect(action_callback)
            layout.addWidget(btn)