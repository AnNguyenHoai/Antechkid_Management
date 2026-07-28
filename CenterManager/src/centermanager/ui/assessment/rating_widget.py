# -*- coding: utf-8 -*-
"""
Rating widget for overall score (0-5 stars).
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


class RatingWidget(QWidget):
    """Star rating widget (0-5)."""
    value_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._setup_ui()
        self.set_value(0)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.buttons = []
        for i in range(5):
            btn = QPushButton("☆")
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 18px;
                    border: none;
                    background: transparent;
                }
                QPushButton:hover {
                    background: #e8e8e8;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i+1: self.set_value(idx))
            layout.addWidget(btn)
            self.buttons.append(btn)

        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                border: none;
                background: transparent;
                color: #999;
            }
            QPushButton:hover {
                color: #333;
            }
        """)
        self.clear_btn.clicked.connect(lambda: self.set_value(0))
        layout.addWidget(self.clear_btn)

    def set_value(self, value: int) -> None:
        """Set rating value (0-5)."""
        value = max(0, min(5, value))
        if value == self._value:
            return
        self._value = value
        self._update_display()
        self.value_changed.emit(value)

    def value(self) -> int:
        return self._value

    def _update_display(self) -> None:
        for i, btn in enumerate(self.buttons):
            if i < self._value:
                btn.setText("★")
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        border: none;
                        background: transparent;
                        color: #f5b342;
                    }
                """)
            else:
                btn.setText("☆")
                btn.setStyleSheet("""
                    QPushButton {
                        font-size: 18px;
                        border: none;
                        background: transparent;
                    }
                    QPushButton:hover {
                        background: #e8e8e8;
                    }
                """)