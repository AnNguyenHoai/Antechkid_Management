# -*- coding: utf-8 -*-
"""
TeacherDashboardPage - Dashboard for Teacher Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QSizePolicy, QListWidget, QListWidgetItem
)

from centermanager.services.teacher_service import TeacherService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.ui.shared import StatisticGrid, SectionHeader, EmptyState, ActivityCard
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class TeacherDashboardPage(QWidget):
    def __init__(
        self,
        teacher_service: TeacherService,
        assignment_service: TeacherAssignmentService,
        timeline_service: TeacherTimelineService,  # <-- thêm
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._teacher_service = teacher_service
        self._assignment_service = assignment_service
        self._timeline_service = timeline_service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {COLORS['background']};")

        container = QWidget()
        container.setStyleSheet(f"background: {COLORS['background']};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        container_layout.setSpacing(SPACING['xl'])

        # Stats grid
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # Recent Activities
        recent_section = QWidget()
        recent_layout = QVBoxLayout(recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(SPACING['sm'])
        recent_header = SectionHeader("Recent Activities")
        recent_layout.addWidget(recent_header)

        self.recent_list = QListWidget()
        self.recent_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.recent_list.setFrameShape(QFrame.Shape.NoFrame)
        self.recent_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 0px;
            }
        """)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.recent_list.setMaximumHeight(340)
        recent_layout.addWidget(self.recent_list)
        container_layout.addWidget(recent_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        try:
            teachers = self._teacher_service.list_teachers()
            total = len(teachers)
            active = sum(1 for t in teachers if t.status == "ACTIVE")
            total_assignments = 0
            for t in teachers:
                total_assignments += len(self._assignment_service.get_assigned_classes(t.id))

            self.stats_grid.set_metrics([
                {"icon": "👨‍🏫", "label": "Total Teachers", "value": str(total)},
                {"icon": "✅", "label": "Active Teachers", "value": str(active)},
                {"icon": "📚", "label": "Total Assignments", "value": str(total_assignments)},
            ])

            self._refresh_recent_activities()

        except Exception as e:
            logger.exception("Failed to refresh teacher dashboard")
            self.stats_grid.set_metrics([
                {"icon": "👨‍🏫", "label": "Total Teachers", "value": "0"},
                {"icon": "✅", "label": "Active Teachers", "value": "0"},
                {"icon": "📚", "label": "Total Assignments", "value": "0"},
            ])

    def _refresh_recent_activities(self) -> None:
        self.recent_list.clear()
        try:
            teachers = self._teacher_service.list_teachers()
            all_events = []
            for t in teachers:
                events = self._timeline_service.get_teacher_timeline(t.id, limit=5)
                for ev in events:
                    all_events.append({
                        'time': ev.created_at,
                        'title': ev.title,
                        'description': ev.description or '',
                        'teacher_name': t.full_name,
                        'event_type': ev.event_type
                    })
            all_events.sort(key=lambda x: x['time'], reverse=True)
            recent = all_events[:10]

            if recent:
                for ev in recent:
                    icon_map = {
                        "TeacherCreated": "👨‍🏫",
                        "TeacherUpdated": "✏️",
                        "TeacherArchived": "🗑️",
                        "TeacherRestored": "🔄",
                        "TeacherAssigned": "📚",
                        "TeacherUnassigned": "🚫",
                        "DocumentUploaded": "📎",
                        "DocumentDeleted": "🗑️",
                    }
                    icon = icon_map.get(ev['event_type'], "📌")
                    subtitle = f"Teacher: {ev['teacher_name']}"
                    card = ActivityCard(
                        icon=icon,
                        title=ev['title'],
                        subtitle=subtitle,
                        time=ev['time']
                    )
                    list_item = QListWidgetItem()
                    list_item.setSizeHint(card.sizeHint())
                    self.recent_list.addItem(list_item)
                    self.recent_list.setItemWidget(list_item, card)
            else:
                empty = EmptyState(
                    icon="📭",
                    title="No recent activities",
                    description="Activities will appear here when teachers are updated."
                )
                list_item = QListWidgetItem()
                list_item.setSizeHint(empty.sizeHint())
                self.recent_list.addItem(list_item)
                self.recent_list.setItemWidget(list_item, empty)
        except Exception as e:
            logger.exception("Failed to load recent activities")
            error_item = QListWidgetItem("⚠️ Unable to load activities")
            self.recent_list.addItem(error_item)