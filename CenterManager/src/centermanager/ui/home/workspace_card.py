# src/centermanager/ui/home/workspace_card.py
# -*- coding: utf-8 -*-
"""
WorkspaceCard - card for Home Workspace with summary and health status.
Now with flexible sizing.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class WorkspaceCard(QFrame):
    clicked = Signal(str)  # workspace_id

    def __init__(
        self,
        workspace_id: str,
        name: str,
        icon: str,
        description: str,
        summary_text: str,
        health_status: str,
        health_details: str,
        quick_action_label: str = "Open →",
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._workspace_id = workspace_id
        self._setup_ui(name, icon, description, summary_text, health_status, health_details, quick_action_label)

    def _setup_ui(self, name: str, icon: str, description: str, summary_text: str, health_status: str, health_details: str, quick_action_label: str) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        border_color = COLORS['gray_300']
        if health_status == "warning":
            border_color = COLORS['warning']
        elif health_status == "critical":
            border_color = COLORS['danger']
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-radius: 12px;
                border: 2px solid {border_color};
                padding: 16px;
            }}
            QFrame:hover {{
                background: {COLORS['gray_100']};
            }}
        """)
        # Set size policy to expand both directions
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(180)  # ensure minimum height

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Top row: icon + name + status indicator
        top_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_large']}px;")
        top_layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text_primary']};")
        top_layout.addWidget(name_label)

        top_layout.addStretch()

        # Status indicator
        status_color = {
            "good": COLORS['success'],
            "warning": COLORS['warning'],
            "critical": COLORS['danger'],
        }.get(health_status, COLORS['gray_400'])
        status_dot = QLabel("●")
        status_dot.setStyleSheet(f"color: {status_color}; font-size: 14px;")
        top_layout.addWidget(status_dot)
        if health_details:
            status_label = QLabel(health_details)
            status_label.setStyleSheet(f"font-size: 12px; color: {status_color};")
            top_layout.addWidget(status_label)

        layout.addLayout(top_layout)

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"font-size: 13px; color: {COLORS['muted']};")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Summary text
        summary_label = QLabel(summary_text)
        summary_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']};")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # Quick action button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.action_btn = QPushButton(quick_action_label)
        self.action_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark']};
            }}
        """)
        self.action_btn.clicked.connect(lambda: self.clicked.emit(self._workspace_id))
        btn_layout.addWidget(self.action_btn)
        layout.addLayout(btn_layout)

        # Make whole card clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self._workspace_id)
        super().mousePressEvent(event)