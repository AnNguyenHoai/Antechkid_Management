# -*- coding: utf-8 -*-
"""
TimelineCard - Displays a timeline event.
Reuses existing TimelineCard but with improved styling.
"""
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget

from centermanager.models.timeline_event import TimelineEvent
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class TimelineCard(QFrame):
    def __init__(self, event: TimelineEvent, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                background: white;
                padding: {SPACING['sm']}px {SPACING['md']}px;
                margin: 2px 0;
            }}
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['xs'])

        header = QHBoxLayout()
        icon_label = QLabel(self._get_icon())
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon']}px;")
        header.addWidget(icon_label)

        title_label = QLabel(self._event.title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['body']}px;
            font-weight: 500;
            color: {COLORS['text_primary']};
        """)
        header.addWidget(title_label)

        header.addStretch()

        time_str = self._format_time(self._event.created_at)
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['muted_light']};
        """)
        header.addWidget(time_label)

        layout.addLayout(header)

        if self._event.description:
            desc_label = QLabel(self._event.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body_small']}px;
                color: {COLORS['text_secondary']};
            """)
            layout.addWidget(desc_label)

        type_label = QLabel(self._event.event_type)
        type_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['muted']};
            background: {COLORS['gray_100']};
            padding: 2px 8px;
            border-radius: 10px;
        """)
        type_label.setFixedHeight(22)
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
            "NoteAdded": "📝",
            "DocumentUploaded": "📎",
            "System": "⚙️",
        }
        return icons.get(self._event.event_type, "📅")

    def _format_time(self, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt_utc = dt.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt.astimezone(timezone.utc)
        dt_local = dt_utc.astimezone()
        now_local = datetime.now().astimezone()

        if dt_local.date() == now_local.date():
            return f"Today {dt_local.strftime('%H:%M')}"
        elif (now_local - dt_local).days == 1:
            return f"Yesterday {dt_local.strftime('%H:%M')}"
        else:
            return dt_local.strftime("%d/%m/%Y %H:%M")