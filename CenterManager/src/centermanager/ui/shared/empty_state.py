# -*- coding: utf-8 -*-
"""
EmptyState - Standard empty state for all workspaces.
Now with optional action button.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class EmptyState(QWidget):
    def __init__(
        self,
        icon: str = "📭",
        title: str = "No data",
        description: str = "",
        action_text: Optional[str] = None,
        action_callback: Optional[callable] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, title, description, action_text, action_callback)

    def _setup_ui(self, icon: str, title: str, description: str, action_text: Optional[str], action_callback: Optional[callable]) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(SPACING['sm'])

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['section_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body']}px;
                color: {COLORS['text_muted']};
            """)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        if action_text and action_callback:
            from centermanager.ui.design_system.components import PrimaryButton
            btn = PrimaryButton(action_text)
            btn.setFixedHeight(36)
            btn.clicked.connect(action_callback)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)