# -*- coding: utf-8 -*-
"""
ClassDashboardPage - Dashboard for Class Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QSizePolicy, QListWidget, QListWidgetItem
)

from centermanager.services.class_service import ClassService
from centermanager.services.session_service import SessionService
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.ui.shared import StatisticGrid, SectionHeader, EmptyState, ActivityCard
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class ClassDashboardPage(QWidget):
    def __init__(
        self,
        class_service: ClassService,
        session_service: SessionService,
        timeline_service: ClassTimelineService,  # <-- thêm
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._session_service = session_service
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

        # Upcoming sessions
        upcoming_section = QWidget()
        upcoming_layout = QVBoxLayout(upcoming_section)
        upcoming_layout.setContentsMargins(0, 0, 0, 0)
        upcoming_layout.setSpacing(SPACING['sm'])
        upcoming_header = SectionHeader("Upcoming Sessions")
        upcoming_layout.addWidget(upcoming_header)
        self.upcoming_label = QLabel("Loading...")
        self.upcoming_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']};")
        upcoming_layout.addWidget(self.upcoming_label)
        container_layout.addWidget(upcoming_section)

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
            classes = self._class_service.list_classes()
            total = len(classes)
            active = sum(1 for c in classes if c.is_active)
            total_students = sum(c.student_count for c in classes)
            upcoming_sessions = 0
            from datetime import date, timedelta
            today = date.today()
            week_later = today + timedelta(days=7)
            for cls in classes:
                sessions = self._session_service.get_sessions_for_class(cls.id)
                upcoming_sessions += sum(1 for s in sessions if today <= s.scheduled_date <= week_later and s.status == "Scheduled")

            self.stats_grid.set_metrics([
                {"icon": "📚", "label": "Total Classes", "value": str(total)},
                {"icon": "✅", "label": "Active Classes", "value": str(active)},
                {"icon": "👨‍🎓", "label": "Total Students", "value": str(total_students)},
                {"icon": "📅", "label": "Upcoming Sessions (7d)", "value": str(upcoming_sessions)},
            ])

            self.upcoming_label.setText(f"{upcoming_sessions} sessions scheduled in the next 7 days.")

            # Recent activities from class timeline
            self._refresh_recent_activities()

        except Exception as e:
            logger.exception("Failed to refresh class dashboard")
            self.stats_grid.set_metrics([
                {"icon": "📚", "label": "Total Classes", "value": "0"},
                {"icon": "✅", "label": "Active Classes", "value": "0"},
                {"icon": "👨‍🎓", "label": "Total Students", "value": "0"},
                {"icon": "📅", "label": "Upcoming Sessions (7d)", "value": "0"},
            ])
            self.upcoming_label.setText("Unable to load data.")

    def _refresh_recent_activities(self) -> None:
        self.recent_list.clear()
        try:
            # Lấy tất cả các lớp và lấy timeline events từ mỗi lớp (giới hạn 5 events mỗi lớp)
            classes = self._class_service.list_classes()
            all_events = []
            for cls in classes:
                events = self._timeline_service.get_class_timeline(cls.id, limit=5)
                for ev in events:
                    all_events.append({
                        'time': ev.created_at,
                        'title': ev.title,
                        'description': ev.description or '',
                        'class_name': cls.name,
                        'event_type': ev.event_type
                    })
            # Sắp xếp theo thời gian giảm dần và lấy 10 mới nhất
            all_events.sort(key=lambda x: x['time'], reverse=True)
            recent = all_events[:10]

            if recent:
                for ev in recent:
                    icon_map = {
                        "ClassCreated": "📚",
                        "ClassUpdated": "✏️",
                        "ClassArchived": "🗑️",
                        "ClassRestored": "🔄",
                        "TeacherAssigned": "👨‍🏫",
                        "TeacherReplaced": "🔄",
                        "TeacherRemoved": "❌",
                        "StudentEnrolled": "👨‍🎓",
                        "StudentRemoved": "🚫",
                        "ScheduleUpdated": "📅",
                    }
                    icon = icon_map.get(ev['event_type'], "📌")
                    subtitle = f"Class: {ev['class_name']}"
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
                    description="Activities will appear here when classes are updated."
                )
                list_item = QListWidgetItem()
                list_item.setSizeHint(empty.sizeHint())
                self.recent_list.addItem(list_item)
                self.recent_list.setItemWidget(list_item, empty)
        except Exception as e:
            logger.exception("Failed to load recent activities")
            error_item = QListWidgetItem("⚠️ Unable to load activities")
            self.recent_list.addItem(error_item)