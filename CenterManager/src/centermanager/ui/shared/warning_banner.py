# -*- coding: utf-8 -*-
"""
WarningBanner - Displays a warning or attention message.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class WarningBanner(QFrame):
    def __init__(
        self,
        message: str,
        icon: str = "⚠️",
        severity: str = "warning",  # "warning", "critical", "info"
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(message, icon, severity)

    def _setup_ui(self, message: str, icon: str, severity: str) -> None:
        colors = {
            "warning": {"bg": "#fff3e0", "border": "#ffb74d", "text": "#e65100"},
            "critical": {"bg": "#ffebee", "border": "#ef9a9a", "text": "#b71c1c"},
            "info": {"bg": "#e3f2fd", "border": "#64b5f6", "text": "#0d47a1"},
        }
        style = colors.get(severity, colors["info"])

        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                background: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: 6px;
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['sm'])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        layout.addWidget(icon_label)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            color: {style['text']};
        """)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)
        layout.addStretch()