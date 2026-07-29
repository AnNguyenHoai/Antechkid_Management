# -*- coding: utf-8 -*-
"""
TimelineCard widget - displays a single timeline event.
Redesigned: smaller, cleaner, better hierarchy.
"""
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame

from centermanager.models.timeline_event import TimelineEvent
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class TimelineCard(QFrame):
    """Card displaying a single timeline event (read-only)."""
    
    def __init__(self, event: TimelineEvent, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._event = event
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {COLORS['border_light']};
                border-radius: {BORDER_RADIUS['sm']}px;
                background: {COLORS['surface']};
                padding: {SPACING['sm']}px {SPACING['md']}px;
                margin: 2px 0;
            }}
            QFrame:hover {{
                background: {COLORS['surface_hover']};
            }}
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['xs'])

        # Header: Icon + Title + Time
        header = QHBoxLayout()
        header.setSpacing(SPACING['sm'])
        
        icon_label = QLabel(self._get_icon())
        icon_label.setStyleSheet(f"font-size: {TYPOGRAPHY['icon_small']}px;")
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
            color: {COLORS['text_muted']};
        """)
        header.addWidget(time_label)

        layout.addLayout(header)

        # Description (if any)
        if self._event.description:
            desc_label = QLabel(self._event.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(f"""
                font-size: {TYPOGRAPHY['body_small']}px;
                color: {COLORS['text_secondary']};
                padding-left: {SPACING['sm']}px;
            """)
            layout.addWidget(desc_label)

        # Event type tag (small, inline)
        type_label = QLabel(self._event.event_type)
        type_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['caption']}px;
            color: {COLORS['text_muted']};
            background: {COLORS['gray_100']};
            padding: 0px {SPACING['sm']}px;
            border-radius: {BORDER_RADIUS['sm']}px;
        """)
        type_label.setFixedHeight(20)
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