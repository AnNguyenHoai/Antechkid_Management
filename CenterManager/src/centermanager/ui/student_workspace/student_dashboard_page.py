# -*- coding: utf-8 -*-
"""
StudentDashboardPage - Complete dashboard for Student Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
)

from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.ui.shared import (
    StatisticGrid, ActivityCard, WarningBanner,
    EmptyState, SectionHeader, ChartCard, MetricCard
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
        analytics_service: StudentAnalyticsService,  # NEW
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = dashboard_service
        self._analytics_service = analytics_service
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

        # ---- Stats Grid ----
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # ---- Charts: Enrollment & Assessment ----
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(SPACING['md'])
        self.enrollment_chart = ChartCard("Enrollment Trend", "bar")
        self.assessment_chart = ChartCard("Assessment Distribution", "pie")
        charts_layout.addWidget(self.enrollment_chart, 1)
        charts_layout.addWidget(self.assessment_chart, 1)
        container_layout.addLayout(charts_layout)

        # ---- Average Score (Metric) ----
        self.avg_score_widget = MetricCard("⭐", "Average Score", "0", "")
        container_layout.addWidget(self.avg_score_widget)

        # ---- Quick Insights (Age Distribution) ----
        insights_header = SectionHeader("Quick Insights")
        container_layout.addWidget(insights_header)
        self.age_chart = ChartCard("Age Distribution", "bar")
        container_layout.addWidget(self.age_chart)

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

        # ---- Recent Students ----
        recent_section = QWidget()
        recent_layout = QVBoxLayout(recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_header = SectionHeader("Recent Students")
        recent_layout.addWidget(recent_header)
        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(3)
        self.recent_table.setHorizontalHeaderLabels(["Code", "Name", "Enrolled"])
        self.recent_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.doubleClicked.connect(self._on_recent_student_double_click)
        recent_layout.addWidget(self.recent_table)
        container_layout.addWidget(recent_section)

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
        logger.debug("Refreshing dashboard...")
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

        self._populate_charts()
        self._populate_attention()
        self._populate_recent_students()

    def _populate_charts(self) -> None:
        try:
            data = self._analytics_service.get_dashboard_analytics()
            self.avg_score_widget.set_value(f"{data['average_score']:.1f}/5")
            self.enrollment_chart.set_data(data['enrollment_trend'])
            self.assessment_chart.set_data(data['assessment_distribution'])
            self.age_chart.set_data(data['age_distribution'])
        except Exception as e:
            logger.exception("Failed to load analytics data")

    def _populate_attention(self) -> None:
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

    def _populate_recent_students(self) -> None:
        try:
            recent = self._analytics_service.get_recent_students(limit=5)
            self.recent_table.setRowCount(len(recent))
            for row, s in enumerate(recent):
                self.recent_table.setItem(row, 0, QTableWidgetItem(s.student_code))
                self.recent_table.setItem(row, 1, QTableWidgetItem(s.full_name))
                self.recent_table.setItem(row, 2, QTableWidgetItem(s.created_at.strftime("%d/%m/%Y")))
            self.recent_table.resizeColumnsToContents()
        except Exception as e:
            logger.exception("Failed to load recent students")

    def _on_recent_student_double_click(self, index) -> None:
        row = index.row()
        try:
            recent = self._analytics_service.get_recent_students(limit=5)
            if row < len(recent):
                self.student_selected.emit(recent[row].id)
        except Exception as e:
            logger.exception("Error opening student detail")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()