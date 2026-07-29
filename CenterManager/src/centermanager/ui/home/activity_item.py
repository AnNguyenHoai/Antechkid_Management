# -*- coding: utf-8 -*-
"""
ActivityItem - a single activity item for Home recent activities.
"""
from typing import Optional
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class ActivityItem(QFrame):
    def __init__(
        self,
        icon: str,
        title: str,
        student_name: str,
        student_code: str,
        time: datetime,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, title, student_name, student_code, time)

    def _setup_ui(self, icon: str, title: str, student_name: str, student_code: str, time: datetime) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                padding: {SPACING['xs']}px 0;
                border-bottom: 1px solid {COLORS['border_light']};
            }}
            QFrame:hover {{
                background: {COLORS['surface_hover']};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING['xs'], SPACING['xs'], SPACING['xs'], SPACING['xs'])
        layout.setSpacing(SPACING['sm'])

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        icon_label.setFixedWidth(28)
        layout.addWidget(icon_label)

        content_layout = QVBoxLayout()
        content_layout.setSpacing(SPACING['xs'])
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: {TYPOGRAPHY['body']}px; font-weight: 500; color: {COLORS['text_primary']};")
        content_layout.addWidget(title_label)

        sub_label = QLabel(f"{student_name} ({student_code})")
        sub_label.setStyleSheet(f"font-size: {TYPOGRAPHY['caption']}px; color: {COLORS['muted']};")
        content_layout.addWidget(sub_label)

        layout.addLayout(content_layout)
        layout.addStretch()

        time_str = self._format_time(time)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"font-size: {TYPOGRAPHY['caption']}px; color: {COLORS['muted_light']};")
        time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(time_label)

    def _format_time(self, dt: datetime) -> str:
        now = datetime.now()
        if dt.date() == now.date():
            return f"Today {dt.strftime('%H:%M')}"
        elif (now - dt).days == 1:
            return f"Yesterday {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%d/%m/%Y %H:%M")