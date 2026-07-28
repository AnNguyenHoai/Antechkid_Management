# -*- coding: utf-8 -*-
"""
TimelineWidget - displays a list of timeline events in the Workspace.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from centermanager.models.timeline_event import TimelineEvent
from centermanager.ui.timeline.timeline_card import TimelineCard

logger = logging.getLogger(__name__)


class TimelineWidget(QWidget):
    """Widget that renders a list of timeline events."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # No initial content
        self._clear()

    def _clear(self) -> None:
        """Remove all child widgets."""
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_events(self, events: List[TimelineEvent]) -> None:
        """Render a list of timeline events."""
        self._clear()
        if not events:
            self._show_empty()
            return

        for event in events:
            card = TimelineCard(event)
            self.layout().addWidget(card)

        # Add a stretch to push cards to top
        self.layout().addStretch()

    def _show_empty(self) -> None:
        """Show empty state."""
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(0, 8, 0, 8)
        empty_layout.setSpacing(4)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel("📅")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        empty_layout.addWidget(icon)

        msg = QLabel("No activity yet.\nTimeline events will appear here.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("color: #999; font-size: 14px;")
        empty_layout.addWidget(msg)

        self.layout().addWidget(empty_widget)
        self.layout().addStretch()