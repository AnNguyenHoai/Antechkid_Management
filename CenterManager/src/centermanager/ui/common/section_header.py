# -*- coding: utf-8 -*-
"""
SectionHeader - a header with title, optional subtitle, and optional action button.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from centermanager.ui import styles


class SectionHeader(QWidget):
    """Section header with title, subtitle, and optional action."""

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
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(8)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(styles.SECTION_TITLE)
        layout.addWidget(title_label)

        # Subtitle
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet(styles.SECTION_SUBTITLE)
            layout.addWidget(sub_label)

        layout.addStretch()

        # Action button
        if action_text and action_callback:
            self.action_btn = QPushButton(action_text)
            self.action_btn.setStyleSheet(styles.BUTTON_PRIMARY)
            self.action_btn.clicked.connect(action_callback)
            layout.addWidget(self.action_btn)