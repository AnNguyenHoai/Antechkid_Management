# -*- coding: utf-8 -*-
"""
StudentDashboardPage - redesigned dashboard using design system components.
Now with Need Attention, Upcoming Events, Quick Insights, and grouped recent activities.
"""
import logging
from typing import Optional
from datetime import datetime, date

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QGridLayout, QLabel, QPushButton, QSizePolicy
)

from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.ui.design_system import (
    StatisticCard, ActivityCard, SectionHeader, EmptyState,
    PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import SPACING, COLORS
from centermanager.ui.common.activity_item import ActivityItem

logger = logging.getLogger(__name__)


class StudentDashboardPage(QWidget):
    add_student_clicked = Signal()
    import_students_clicked = Signal()
    export_students_clicked = Signal()
    student_selected = Signal(int)

    def __init__(
        self,
        dashboard_service: StudentDashboardService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = dashboard_service
        self._setup_ui()
        QTimer.singleShot(100, self.refresh)

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
        container_layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        container_layout.setSpacing(SPACING['lg'])

        # ---- Stats grid ----
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(SPACING['xs'])
        self.stats_grid.setContentsMargins(0, 0, 0, 0)

        self.stat_cards = []
        stat_data = [
            ("👥", "Total Students", "0"),
            ("✅", "Active", "0"),
            ("📦", "Archived", "0"),
            ("🌟", "New This Month", "0"),
        ]
        for i, (icon, label, default) in enumerate(stat_data):
            card = StatisticCard(icon, label, default)
            self.stat_cards.append(card)
            self.stats_grid.addWidget(card, i // 2, i % 2)
        container_layout.addLayout(self.stats_grid)

        # ---- Quick Insights ----
        self.insights_section = QWidget()
        insights_layout = QVBoxLayout(self.insights_section)
        insights_layout.setContentsMargins(0, 0, 0, 0)
        insights_layout.setSpacing(SPACING['sm'])
        insights_header = SectionHeader("Quick Insights", subtitle="Key metrics at a glance")
        insights_layout.addWidget(insights_header)
        self.insights_container = QWidget()
        self.insights_container_layout = QGridLayout(self.insights_container)
        self.insights_container_layout.setSpacing(SPACING['sm'])
        insights_layout.addWidget(self.insights_container)
        container_layout.addWidget(self.insights_section)

        # ---- Need Attention ----
        self.attention_section = QWidget()
        attention_layout = QVBoxLayout(self.attention_section)
        attention_layout.setContentsMargins(0, 0, 0, 0)
        attention_layout.setSpacing(SPACING['sm'])
        att_header = SectionHeader(
            "Need Attention",
            subtitle="Students requiring follow-up"
        )
        attention_layout.addWidget(att_header)
        self.attention_container = QWidget()
        self.attention_container_layout = QVBoxLayout(self.attention_container)
        self.attention_container_layout.setContentsMargins(0, 0, 0, 0)
        self.attention_container_layout.setSpacing(SPACING['xs'])
        attention_layout.addWidget(self.attention_container)
        container_layout.addWidget(self.attention_section)

        # ---- Upcoming Events ----
        self.events_section = QWidget()
        events_layout = QVBoxLayout(self.events_section)
        events_layout.setContentsMargins(0, 0, 0, 0)
        events_layout.setSpacing(SPACING['sm'])
        events_header = SectionHeader("Upcoming Events")
        events_layout.addWidget(events_header)
        self.events_container = QWidget()
        self.events_container_layout = QVBoxLayout(self.events_container)
        self.events_container_layout.setContentsMargins(0, 0, 0, 0)
        self.events_container_layout.setSpacing(SPACING['xs'])
        events_layout.addWidget(self.events_container)
        container_layout.addWidget(self.events_section)

        # ---- Recent Activities (grouped) ----
        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(SPACING['sm'])
        recent_header = SectionHeader("Recent Activities")
        recent_layout.addWidget(recent_header)
        self.recent_container = QWidget()
        self.recent_container_layout = QVBoxLayout(self.recent_container)
        self.recent_container_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_container_layout.setSpacing(SPACING['xs'])
        recent_layout.addWidget(self.recent_container)
        container_layout.addWidget(self.recent_section)

        # ---- Quick Actions ----
        actions_section = QWidget()
        actions_layout = QHBoxLayout(actions_section)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING['sm'])

        add_btn = PrimaryButton("➕ Add Student")
        add_btn.clicked.connect(self.add_student_clicked.emit)
        import_btn = SecondaryButton("📥 Import")
        import_btn.clicked.connect(self.import_students_clicked.emit)
        export_btn = SecondaryButton("📤 Export")
        export_btn.clicked.connect(self.export_students_clicked.emit)

        actions_layout.addWidget(add_btn)
        actions_layout.addWidget(import_btn)
        actions_layout.addWidget(export_btn)
        actions_layout.addStretch()
        container_layout.addWidget(actions_section)

        container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        logger.debug("Refreshing dashboard...")
        try:
            stats = self._service.get_stats()
            self.stat_cards[0].set_value(str(stats.total))
            self.stat_cards[1].set_value(str(stats.active))
            self.stat_cards[2].set_value(str(stats.archived))
            self.stat_cards[3].set_value(str(stats.new_this_month))
        except Exception as e:
            logger.exception("Failed to get dashboard stats")

        self._populate_insights()
        self._populate_attention()
        self._populate_events()
        self._populate_recent_activities()

    def _populate_insights(self) -> None:
        self._clear_layout(self.insights_container_layout)
        try:
            insights = self._service.get_quick_insights()
            items = [
                (f"📊 {insights.avg_assessment_score}/5", "Avg Assessment Score"),
                (f"🎂 {insights.avg_age}", "Avg Age"),
                (f"👨‍👩‍👧 {insights.total_parents}", "Total Parents"),
                (f"✅ {insights.assessment_completion_rate}%", "Assessment Completion"),
            ]
            row, col = 0, 0
            for label, detail in items:
                widget = QWidget()
                layout = QVBoxLayout(widget)
                layout.setContentsMargins(8, 4, 8, 4)
                label_w = QLabel(label)
                label_w.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text_primary']};")
                detail_w = QLabel(detail)
                detail_w.setStyleSheet(f"font-size: 12px; color: {COLORS['muted']};")
                layout.addWidget(label_w)
                layout.addWidget(detail_w)
                self.insights_container_layout.addWidget(widget, row, col)
                col += 1
                if col >= 2:
                    col = 0
                    row += 1
        except Exception as e:
            logger.exception("Failed to load insights")

    def _populate_attention(self) -> None:
        self._clear_layout(self.attention_container_layout)
        try:
            attention = self._service.get_students_requiring_attention(limit=10)
            if attention:
                for item in attention:
                    btn = SecondaryButton(
                        f"⚠️ {item.full_name} ({item.student_code}) – {item.reason}"
                    )
                    btn.setStyleSheet(btn.styleSheet() + """
                        QPushButton {
                            text-align: left;
                            padding: 8px 12px;
                            background: #fff3e0;
                            border-color: #ffe0b2;
                        }
                        QPushButton:hover {
                            background: #ffe0b2;
                        }
                    """)
                    btn.clicked.connect(
                        lambda checked, sid=item.student_id: self.student_selected.emit(sid)
                    )
                    self.attention_container_layout.addWidget(btn)
            else:
                empty = EmptyState(
                    icon="✅",
                    title="All good!",
                    description="No students require attention."
                )
                self.attention_container_layout.addWidget(empty)
        except Exception as e:
            logger.exception("Failed to load attention students")

    def _populate_events(self) -> None:
        self._clear_layout(self.events_container_layout)
        try:
            events = self._service.get_upcoming_events()
            if events:
                for ev in events:
                    icon_map = {
                        "birthday": "🎂",
                        "assessment": "📊",
                        "session": "📚",
                    }
                    icon = icon_map.get(ev.event_type, "📌")
                    label = QLabel(f"{icon} {ev.details} – {ev.date.strftime('%d/%m/%Y')}")
                    if ev.student_name:
                        label.setText(f"{icon} {ev.student_name} ({ev.student_code}) – {ev.details} – {ev.date.strftime('%d/%m/%Y')}")
                    label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']}; padding: 2px 0;")
                    self.events_container_layout.addWidget(label)
            else:
                empty = EmptyState(
                    icon="📅",
                    title="No upcoming events",
                    description="Events will appear here when scheduled."
                )
                self.events_container_layout.addWidget(empty)
        except Exception as e:
            logger.exception("Failed to load upcoming events")

    def _populate_recent_activities(self) -> None:
        self._clear_layout(self.recent_container_layout)
        try:
            activities = self._service.get_recent_activities(limit=12)
            if activities:
                # Group by day
                today = date.today()
                yesterday = today - timedelta(days=1)
                groups = {"Today": [], "Yesterday": [], "Older": []}
                for act in activities:
                    dt = act.time.date()
                    if dt == today:
                        groups["Today"].append(act)
                    elif dt == yesterday:
                        groups["Yesterday"].append(act)
                    else:
                        groups["Older"].append(act)
                for group_name, acts in groups.items():
                    if acts:
                        header = QLabel(group_name)
                        header.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS['muted']}; padding: 4px 0;")
                        self.recent_container_layout.addWidget(header)
                        for act in acts:
                            item = ActivityItem(
                                icon=act.icon,
                                title=act.title,
                                student_name=act.student_name,
                                student_code=act.student_code,
                                time=act.time
                            )
                            self.recent_container_layout.addWidget(item)
            else:
                empty = EmptyState(
                    icon="📭",
                    title="No recent activities",
                    description="Activities will appear here when students are updated."
                )
                self.recent_container_layout.addWidget(empty)
        except Exception as e:
            logger.exception("Failed to load recent activities")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()