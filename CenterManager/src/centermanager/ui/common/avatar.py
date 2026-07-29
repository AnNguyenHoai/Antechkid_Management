# -*- coding: utf-8 -*-
"""
Avatar - circular avatar with initials.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class Avatar(QLabel):
    """Circular avatar displaying initials of a name."""

    def __init__(
        self,
        name: str,
        size: int = 32,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._size = size
        self._setup_ui()

    def _setup_ui(self) -> None:
        initials = self._get_initials(self._name)
        self.setText(initials)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(self._size, self._size)
        font_size = max(10, self._size // 2)
        self.setStyleSheet(f"""
            QLabel {{
                background: #1976d2;
                color: white;
                font-size: {font_size}px;
                font-weight: 600;
                border-radius: {self._size // 2}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _get_initials(self, name: str) -> str:
        parts = name.strip().split()
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def set_name(self, name: str) -> None:
        self._name = name
        self.setText(self._get_initials(name))