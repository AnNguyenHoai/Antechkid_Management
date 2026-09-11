# -*- coding: utf-8 -*-
"""
WorkspaceHeader - header for a workspace showing current context and actions.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)

from centermanager.ui.design_system.tokens import COLORS
from centermanager.ui.design_system.components import SecondaryButton


class WorkspaceHeader(QWidget):
    """Header displaying workspace name, current page, and actions."""

    back_home_clicked = Signal()

    def __init__(
        self,
        workspace_name: str,
        current_page_label: str = "",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._workspace_name = workspace_name
        self._current_page = current_page_label
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: white;
                border-bottom: 1px solid {COLORS['gray_200']};
                padding: 8px 16px;
            }}
        """)
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Home button
        self.home_btn = SecondaryButton("🏠 Home")
        self.home_btn.setFixedHeight(32)
        self.home_btn.clicked.connect(self.back_home_clicked.emit)
        layout.addWidget(self.home_btn)

        # Separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {COLORS['gray_300']};")
        layout.addWidget(sep)

        # Workspace name and page
        self.context_label = QLabel(f"{self._workspace_name} / {self._current_page}")
        self.context_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 500;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(self.context_label)

        layout.addStretch()

        # (Đã xóa nút Change Password)

    def set_context(self, workspace_name: str, page_label: str) -> None:
        self._workspace_name = workspace_name
        self._current_page = page_label
        self.context_label.setText(f"{workspace_name} / {page_label}")