# -*- coding: utf-8 -*-
"""StudentDashboardPage - Dashboard focuses on 'What requires my attention today?'"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QPushButton, QSizePolicy, QListWidget, QListWidgetItem
)

from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.ui.shared import (
    MetricCard, StatisticGrid, ActivityCard, WarningBanner,
    EmptyState, SectionHeader
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.design_system.components import PrimaryButton, SecondaryButton

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
        container_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        container_layout.setSpacing(SPACING['xl'])

        # ---- KPI stats ----
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # ---- Today Summary ----
        self.today_section = QWidget()
        today_layout = QVBoxLayout(self.today_section)
        today_layout.setContentsMargins(0, 0, 0, 0)
        today_layout.setSpacing(SPACING['sm'])
        today_header = SectionHeader("Today's Summary")
        today_layout.addWidget(today_header)
        self.today_container = QWidget()
        self.today_container_layout = QVBoxLayout(self.today_container)
        self.today_container_layout.setContentsMargins(0, 0, 0, 0)
        self.today_container_layout.setSpacing(SPACING['xs'])
        today_layout.addWidget(self.today_container)
        container_layout.addWidget(self.today_section)

        # ---- Quick Insights ----
        self.insights_section = QWidget()
        insights_layout = QVBoxLayout(self.insights_section)
        insights_layout.setContentsMargins(0, 0, 0, 0)
        insights_layout.setSpacing(SPACING['sm'])
        insights_header = SectionHeader("Quick Insights")
        insights_layout.addWidget(insights_header)
        self.insights_grid = StatisticGrid()
        insights_layout.addWidget(self.insights_grid)
        container_layout.addWidget(self.insights_section)

        # ---- Need Attention ----
        self.attention_section = QWidget()
        attention_layout = QVBoxLayout(self.attention_section)
        attention_layout.setContentsMargins(0, 0, 0, 0)
        attention_layout.setSpacing(SPACING['sm'])
        att_header = SectionHeader("Need Attention", subtitle="Students requiring follow-up")
        attention_layout.addWidget(att_header)
        self.attention_container = QWidget()
        self.attention_container_layout = QVBoxLayout(self.attention_container)
        self.attention_container_layout.setContentsMargins(0, 0, 0, 0)
        self.attention_container_layout.setSpacing(SPACING['sm'])
        attention_layout.addWidget(self.attention_container)
        container_layout.addWidget(self.attention_section)

        # ---- Upcoming Events ----
        self.events_section = QWidget()
        events_layout = QVBoxLayout(self.events_section)
        events_layout.setContentsMargins(0, 0, 0, 0)
        events_layout.setSpacing(SPACING['sm'])
        events_header = SectionHeader("Upcoming Events")
        events_layout.addWidget(events_header)

        self.events_list = QListWidget()
        self.events_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.events_list.setFrameShape(QFrame.Shape.NoFrame)
        self.events_list.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 0px;
            }
        """)
        self.events_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.events_list.setMaximumHeight(220)
        events_layout.addWidget(self.events_list)
        container_layout.addWidget(self.events_section)

        # ---- Recent Activities ----
        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
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
        container_layout.addWidget(self.recent_section)

        # ---- Quick Actions ----
        actions_section = QWidget()
        actions_layout = QHBoxLayout(actions_section)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING['sm'])

        add_btn = PrimaryButton("➕ Add Student")
        add_btn.setFixedHeight(38)
        add_btn.clicked.connect(self.add_student_clicked.emit)
        import_btn = SecondaryButton("📥 Import")
        import_btn.setFixedHeight(38)
        import_btn.clicked.connect(self.import_students_clicked.emit)
        export_btn = SecondaryButton("📤 Export")
        export_btn.setFixedHeight(38)
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
        try:
            self._refresh_kpis()
            self._refresh_today_summary()
            self._refresh_insights()
            self._refresh_attention()
            self._refresh_events()
            self._refresh_recent_activities()
        except Exception as e:
            logger.exception("Error refreshing dashboard")

    def _refresh_kpis(self) -> None:
        try:
            stats = self._service.get_stats()
            self.stats_grid.set_metrics([
                {"icon": "👥", "label": "Total Students", "value": str(stats.total)},
                {"icon": "✅", "label": "Active", "value": str(stats.active)},
                {"icon": "📦", "label": "Archived", "value": str(stats.archived)},
                {"icon": "🌟", "label": "New This Month", "value": str(stats.new_this_month)},
            ])
        except Exception as e:
            logger.exception("Failed to get dashboard stats")

    def _refresh_today_summary(self) -> None:
        self._clear_layout(self.today_container_layout)
        try:
            summary = self._service.get_today_summary()
            items = [
                (f"📚 {summary.today_classes} classes today", "Scheduled classes"),
                (f"📊 {summary.today_assessments} assessments today", "Assessments recorded"),
                (f"🎂 {len(summary.today_birthdays)} birthdays today", ", ".join(summary.today_birthdays) if summary.today_birthdays else "None"),
                (f"📅 {summary.upcoming_sessions} upcoming sessions", "Next 7 days"),
                (f"⚠️ {len(summary.pending_tasks)} pending tasks", "Students needing attention"),
            ]
            for label, detail in items:
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.setContentsMargins(0, 2, 0, 2)
                label_w = QLabel(label)
                label_w.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {COLORS['text_primary']};")
                detail_w = QLabel(detail)
                detail_w.setStyleSheet(f"font-size: 12px; color: {COLORS['muted']};")
                layout.addWidget(label_w)
                layout.addWidget(detail_w)
                layout.addStretch()
                self.today_container_layout.addWidget(widget)
        except Exception as e:
            logger.exception("Failed to load today summary")

    def _refresh_insights(self) -> None:
        try:
            insights = self._service.get_quick_insights()
            self.insights_grid.set_metrics([
                {"icon": "📊", "label": "Avg Assessment", "value": f"{insights.avg_assessment_score}/5"},
                {"icon": "🎂", "label": "Avg Age", "value": str(insights.avg_age)},
                {"icon": "👨‍👩‍👧", "label": "Parent Coverage", "value": f"{insights.assessment_completion_rate}%"},
            ], columns=3)
        except Exception as e:
            logger.exception("Failed to load insights")

    def _refresh_attention(self) -> None:
        self._clear_layout(self.attention_container_layout)
        try:
            attention = self._service.get_students_requiring_attention(limit=10)
            if attention:
                for item in attention:
                    banner = WarningBanner(
                        message=f"{item.full_name} ({item.student_code}) – {item.reason}",
                        icon="⚠️",
                        severity="warning",
                        action_text="Open →",
                        action_data=item.student_id
                    )
                    banner.clicked.connect(lambda sid: self.student_selected.emit(sid))
                    self.attention_container_layout.addWidget(banner)
            else:
                empty = EmptyState(
                    icon="✅",
                    title="All good!",
                    description="No students require attention."
                )
                self.attention_container_layout.addWidget(empty)
        except Exception as e:
            logger.exception("Failed to load attention students")

    def _refresh_events(self) -> None:
        self.events_list.clear()
        try:
            events = self._service.get_upcoming_events()
            if events:
                for ev in events[:10]:
                    icon_map = {"birthday": "🎂", "assessment": "📊", "session": "📚"}
                    icon = icon_map.get(ev.event_type, "📌")
                    label_text = f"{icon} {ev.details} – {ev.date.strftime('%d/%m/%Y')}"
                    if ev.student_name:
                        label_text = f"{icon} {ev.student_name} ({ev.student_code}) – {ev.details} – {ev.date.strftime('%d/%m/%Y')}"
                    label = QLabel(label_text)
                    label.setStyleSheet(f"""
                        font-size: 13px;
                        color: {COLORS['text_secondary']};
                        padding: 4px 0;
                    """)
                    list_item = QListWidgetItem()
                    list_item.setSizeHint(label.sizeHint())
                    self.events_list.addItem(list_item)
                    self.events_list.setItemWidget(list_item, label)
            else:
                empty = EmptyState(
                    icon="📅",
                    title="No upcoming events",
                    description="Events will appear here when scheduled."
                )
                list_item = QListWidgetItem()
                list_item.setSizeHint(empty.sizeHint())
                self.events_list.addItem(list_item)
                self.events_list.setItemWidget(list_item, empty)
        except Exception as e:
            logger.exception("Failed to load upcoming events")

    def _refresh_recent_activities(self) -> None:
        self.recent_list.clear()
        try:
            activities = self._service.get_recent_activities(limit=10)
            if activities:
                for act in activities:
                    card = ActivityCard(
                        icon="📌",
                        title=act.title,
                        subtitle=f"{act.student_name} ({act.student_code})",
                        time=act.time
                    )
                    list_item = QListWidgetItem()
                    list_item.setSizeHint(card.sizeHint())
                    self.recent_list.addItem(list_item)
                    self.recent_list.setItemWidget(list_item, card)
            else:
                empty = EmptyState(
                    icon="📭",
                    title="No recent activities",
                    description="Activities will appear here when students are updated."
                )
                list_item = QListWidgetItem()
                list_item.setSizeHint(empty.sizeHint())
                self.recent_list.addItem(list_item)
                self.recent_list.setItemWidget(list_item, empty)
        except Exception as e:
            logger.exception("Failed to load recent activities")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()