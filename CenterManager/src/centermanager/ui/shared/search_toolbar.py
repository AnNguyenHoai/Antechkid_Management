# -*- coding: utf-8 -*-
"""
SearchToolbar - Search input with optional filters.
"""
from typing import Optional, List, Dict

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QComboBox, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, SPACING


class SearchToolbar(QWidget):
    search_changed = Signal(str)
    filter_changed = Signal(dict)

    def __init__(
        self,
        placeholder: str = "Search...",
        filters: Optional[List[Dict[str, List[str]]]] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._filters = filters or []
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(f"🔍 {placeholder}")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: white;
                border: 1px solid {COLORS['border']};
                border-radius: 20px;
                padding: 6px 14px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
                outline: none;
            }}
        """)
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.search_input)

        for filter_config in self._filters:
            name = filter_config.get('name', '')
            options = filter_config.get('options', [])
            combo = QComboBox()
            combo.addItems(['All'] + options)
            combo.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 13px;
                    min-width: 100px;
                }}
            """)
            combo.currentTextChanged.connect(
                lambda text, key=name: self.filter_changed.emit({key: text if text != 'All' else ''})
            )
            layout.addWidget(combo)

        layout.addStretch()

        clear_btn = QPushButton("✕ Clear")
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['muted']};
                border: none;
                font-size: 13px;
            }}
            QPushButton:hover {{
                color: {COLORS['text_primary']};
            }}
        """)
        clear_btn.clicked.connect(self.clear)
        layout.addWidget(clear_btn)

    def clear(self) -> None:
        self.search_input.clear()
        for i in range(self.layout().count()):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)

    def text(self) -> str:
        return self.search_input.text()