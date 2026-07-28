# -*- coding: utf-8 -*-
"""
TimelineCard widget - displays a single timeline event.
"""
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from centermanager.models.timeline_event import TimelineEvent


class TimelineCard(QFrame):
    """Card displaying a single timeline event (read-only)."""

    def __init__(self, event: TimelineEvent, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: #fafafa;
                padding: 6px 10px;
                margin: 2px 0;
            }
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        # Header: Icon + Title + Time
        header = QHBoxLayout()
        icon_label = QLabel(self._get_icon())
        icon_label.setStyleSheet("font-size: 16px;")
        header.addWidget(icon_label)

        title_label = QLabel(self._event.title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        header.addWidget(title_label)

        header.addStretch()

        # Format time (convert UTC to local)
        time_str = self._format_time(self._event.created_at)
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(time_label)

        layout.addLayout(header)

        # Description (if any)
        if self._event.description:
            desc_label = QLabel(self._event.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #555; font-size: 13px;")
            layout.addWidget(desc_label)

        # Event type tag
        type_label = QLabel(self._event.event_type)
        type_label.setStyleSheet("""
            color: #666;
            font-size: 11px;
            background-color: #e8e8e8;
            padding: 0px 6px;
            border-radius: 3px;
        """)
        layout.addWidget(type_label)

    def _get_icon(self) -> str:
        icons = {
            "StudentCreated": "🌟",
            "StudentUpdated": "✏️",
            "ParentAdded": "👨‍👩‍👧",
            "ParentUpdated": "✏️",
            "ParentDeleted": "🗑️",
            "AssessmentCreated": "📊",
            "AssessmentUpdated": "✏️",
            "AssessmentDeleted": "🗑️",
            "ProductAdded": "📁",
            "AttachmentAdded": "📎",
            "System": "⚙️",
        }
        return icons.get(self._event.event_type, "📅")

    def _format_time(self, dt: datetime) -> str:
        """Format datetime for display, converting UTC to local time."""
        # Convert UTC to local time (naive -> aware -> local)
        # SQLite stores naive UTC, so we assume dt is UTC
        if dt.tzinfo is None:
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt.astimezone(timezone.utc)
        # Convert to local timezone
        dt_local = dt_utc.astimezone()
        now_local = datetime.now().astimezone()

        # Compare dates in local timezone
        if dt_local.date() == now_local.date():
            return f"Today {dt_local.strftime('%H:%M')}"
        elif (now_local - dt_local).days == 1:
            return f"Yesterday {dt_local.strftime('%H:%M')}"
        else:
            return dt_local.strftime("%d/%m/%Y %H:%M")