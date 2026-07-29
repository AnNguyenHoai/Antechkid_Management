# -*- coding: utf-8 -*-
"""
SearchBar - styled search input with icon and clear button.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QSizePolicy

from centermanager.ui import styles


class SearchBar(QWidget):
    """Search bar with icon and clear button."""

    text_changed = Signal(str)

    def __init__(
        self,
        placeholder: str = "Search by Code, Name, Phone, Parent...",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search input
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setStyleSheet(styles.SEARCH_BAR)
        self.input.setFixedHeight(36)
        self.input.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self.input)

        # Clear button (hidden initially)
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setStyleSheet(styles.BUTTON_ICON)
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(self._clear)
        layout.addWidget(self.clear_btn)

        # Search icon (could be a label, but we'll just use text in placeholder)

    def _clear(self) -> None:
        self.input.clear()
        self.input.setFocus()

    def text(self) -> str:
        return self.input.text()

    def set_text(self, text: str) -> None:
        self.input.setText(text)

    def _on_text_changed(self, text: str) -> None:
        self.clear_btn.setVisible(bool(text))
        self.text_changed.emit(text)