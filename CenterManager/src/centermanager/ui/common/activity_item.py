# -*- coding: utf-8 -*-
"""
ActivityItem - a single activity in the recent activity feed.
"""
from typing import Optional
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QSizePolicy

from centermanager.ui import styles


class ActivityItem(QFrame):
    """A single activity item with icon, title, student, and time."""

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
        self.setStyleSheet("""
            QFrame {
                background: transparent;
                padding: 6px 0;
                border-bottom: 1px solid #f0f0f0;
            }
            QFrame:hover {
                background: #f8f9fa;
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        # Icon
        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 18px;")
        icon_label.setFixedWidth(32)
        layout.addWidget(icon_label)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setStyleSheet(styles.ACTIVITY_TITLE)
        content_layout.addWidget(title_label)

        subtitle = f"{student_name} ({student_code})"
        sub_label = QLabel(subtitle)
        sub_label.setStyleSheet(styles.ACTIVITY_SUBTITLE)
        content_layout.addWidget(sub_label)

        layout.addLayout(content_layout)

        layout.addStretch()

        # Time
        time_str = self._format_time(time)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(styles.ACTIVITY_TIME)
        time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(time_label)

    def _format_time(self, dt: datetime) -> str:
        now = datetime.now()
        if dt.date() == now.date():
            return f"Today {dt.strftime('%H:%M')}"
        elif (now - dt).days == 1:
            return f"Yesterday {dt.strftime('%H:%M')}"
        else:
            return dt.strftime("%d/%m/%Y %H:%M")