# -*- coding: utf-8 -*-
"""
WarningBanner - Displays a warning or attention message as a clickable card.
"""
from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget, QSizePolicy, QPushButton

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class WarningBanner(QFrame):
    clicked = Signal(object)  # Can emit associated data
    
    def __init__(
        self,
        message: str,
        icon: str = "⚠️",
        severity: str = "warning",
        action_text: Optional[str] = "Open →",
        action_data: Optional[object] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._action_data = action_data
        self._setup_ui(message, icon, severity, action_text)

    def _setup_ui(self, message: str, icon: str, severity: str, action_text: Optional[str]) -> None:
        colors = {
            "warning": {"bg": "#fff8e1", "border": "#ffcc02", "text": "#e65100", "icon": "⚠️"},
            "critical": {"bg": "#ffebee", "border": "#ef9a9a", "text": "#b71c1c", "icon": "🚨"},
            "info": {"bg": "#e3f2fd", "border": "#64b5f6", "text": "#0d47a1", "icon": "ℹ️"},
        }
        style = colors.get(severity, colors["info"])
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                background: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: {BORDER_RADIUS['md']}px;
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
            QFrame:hover {{
                background: {style['bg']};
                border-color: {style['border']};
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING['md'], SPACING['sm'], SPACING['md'], SPACING['sm'])
        layout.setSpacing(SPACING['sm'])

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        layout.addWidget(icon_label)

        # Message (with bold first part)
        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            color: {style['text']};
            font-weight: 500;
        """)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        layout.addStretch()

        # Action button
        if action_text:
            action_btn = QPushButton(action_text)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['primary']};
                    border: none;
                    font-size: {TYPOGRAPHY['body_small']}px;
                    font-weight: 600;
                    padding: {SPACING['xs']}px {SPACING['sm']}px;
                }}
                QPushButton:hover {{
                    text-decoration: underline;
                    background: transparent;
                }}
            """)
            action_btn.clicked.connect(self._on_click)
            layout.addWidget(action_btn)

    def _on_click(self) -> None:
        self.clicked.emit(self._action_data)
    
    def mousePressEvent(self, event) -> None:
        self._on_click()
        super().mousePressEvent(event)