# -*- coding: utf-8 -*-
"""
TimelineFeedPage - Display all timeline events with filters and search.
"""
import logging
from typing import Optional, List
from datetime import datetime, date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel,
    QPushButton, QHBoxLayout
)

from centermanager.models.timeline_event import TimelineEvent
from centermanager.services.timeline_service import TimelineService
from centermanager.services.student_service import StudentService
from centermanager.ui.shared import (
    EmptyState, SearchToolbar, SectionHeader, TimelineCard
)
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class TimelineFeedPage(QWidget):
    student_selected = Signal(int)

    def __init__(
        self,
        timeline_service: TimelineService,
        student_service: StudentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._timeline_service = timeline_service
        self._student_service = student_service
        self._events: List[TimelineEvent] = []
        self._filtered: List[TimelineEvent] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: white; padding: {SPACING['sm']}px {SPACING['md']}px; border-bottom: 1px solid {COLORS['border_light']};")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['xs'])

        event_types = ["StudentCreated", "StudentUpdated", "ParentAdded", "AssessmentCreated", "NoteAdded", "DocumentUploaded", "System"]
        self.search_toolbar = SearchToolbar(
            placeholder="Search by student name or event...",
            filters=[
                {"name": "type", "options": event_types},
            ]
        )
        self.search_toolbar.search_changed.connect(self._filter)
        self.search_toolbar.filter_changed.connect(self._apply_filters)
        toolbar_layout.addWidget(self.search_toolbar)

        layout.addWidget(toolbar)

        # Count label
        self.count_label = QLabel("0 events")
        self.count_label.setStyleSheet(f"padding: {SPACING['xs']}px {SPACING['md']}px; font-size: 12px; color: {COLORS['muted']};")
        layout.addWidget(self.count_label)

        # Feed container
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh(self) -> None:
        try:
            # Get all events from all students (need a method to get all events)
            # We'll use a workaround: get all students and their events
            students = self._student_service.list_students()
            all_events = []
            for student in students:
                events = self._timeline_service.get_student_timeline(student.id)
                all_events.extend(events)
            # Sort by created_at descending
            all_events.sort(key=lambda e: e.created_at, reverse=True)
            self._events = all_events
        except Exception as e:
            logger.exception("Failed to load timeline events")
            self._events = []
        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_container()
        self.count_label.setText(f"{len(self._events)} events")

        if not self._events:
            empty = EmptyState(
                icon="📅",
                title="No timeline events",
                description="Events will appear here as activities occur."
            )
            self.container_layout.addWidget(empty)
            return

        for event in self._events:
            card = TimelineCard(event)
            # Make student name clickable? For now, just display.
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _filter(self, text: str) -> None:
        # Simple filter by student name/code or event title
        if not text.strip():
            self._filtered = self._events[:]
            self._update_filtered_ui()
            return
        lower = text.strip().lower()
        self._filtered = [
            e for e in self._events
            if lower in e.title.lower() or
               (e.student and (lower in e.student.full_name.lower() or lower in e.student.student_code.lower()))
        ]
        self._update_filtered_ui()

    def _apply_filters(self, filters: dict) -> None:
        # Apply type filter
        event_type = filters.get('type', '')
        if event_type:
            self._filtered = [e for e in self._events if e.event_type == event_type]
        else:
            self._filtered = self._events[:]
        self._update_filtered_ui()

    def _update_filtered_ui(self) -> None:
        self._clear_container()
        self.count_label.setText(f"{len(self._filtered)} events")

        if not self._filtered:
            empty = EmptyState(
                icon="🔍",
                title="No matching events",
                description="Try adjusting your search or filters."
            )
            self.container_layout.addWidget(empty)
            return

        for event in self._filtered:
            card = TimelineCard(event)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()