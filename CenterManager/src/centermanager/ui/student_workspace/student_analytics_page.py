# -*- coding: utf-8 -*-
"""Student analytics page aligned with UI-PROD-08 feedback and controls."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.ui.design_system.feedback import FeedbackController
from centermanager.ui.design_system.foundation import Button, ButtonVariant
from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.shared import ChartCard, MetricCard

logger = logging.getLogger(__name__)


class StudentAnalyticsPage(QWidget):
    def __init__(
        self,
        analytics_service: StudentAnalyticsService,
        parent: Optional[QWidget] = None,
        feedback_controller: Optional[FeedbackController] = None,
    ) -> None:
        super().__init__(parent)
        self._service = analytics_service
        self._feedback = feedback_controller or FeedbackController(self)
        self._setup_ui()
        self.refresh()

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        self._feedback = controller

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(SPACING["xl"])
        container_layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])

        self.summary_grid = QHBoxLayout()
        self.summary_grid.setSpacing(SPACING["md"])
        self.avg_score_widget = MetricCard("Score", "Average Score", "0", "")
        self.total_students_widget = MetricCard("Students", "Total Students", "0", "")
        self.growth_widget = MetricCard("Growth", "Monthly Growth", "0%", "")
        self.summary_grid.addWidget(self.avg_score_widget)
        self.summary_grid.addWidget(self.total_students_widget)
        self.summary_grid.addWidget(self.growth_widget)
        container_layout.addLayout(self.summary_grid)

        chart_grid = QHBoxLayout()
        chart_grid.setSpacing(SPACING["md"])
        self.enrollment_chart = ChartCard("Enrollment Trend", "bar")
        self.assessment_chart = ChartCard("Assessment Distribution", "pie")
        chart_grid.addWidget(self.enrollment_chart, 1)
        chart_grid.addWidget(self.assessment_chart, 1)
        container_layout.addLayout(chart_grid)

        chart_grid2 = QHBoxLayout()
        chart_grid2.setSpacing(SPACING["md"])
        self.age_chart = ChartCard("Age Distribution", "bar")
        self.score_chart = ChartCard("Score Distribution", "bar")
        chart_grid2.addWidget(self.age_chart, 1)
        chart_grid2.addWidget(self.score_chart, 1)
        container_layout.addLayout(chart_grid2)

        export_section = QHBoxLayout()
        export_section.addStretch()
        self.export_btn = Button("Export analytics report", variant=ButtonVariant.SECONDARY)
        self.export_btn.clicked.connect(self._export_report)
        export_section.addWidget(self.export_btn)
        container_layout.addLayout(export_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        try:
            data = self._service.get_dashboard_analytics()
            self.avg_score_widget.set_value(f"{data.get('average_score', 0):.1f}/5")
            self.total_students_widget.set_value(str(data.get("total_students", 0)))
            growth = data.get("monthly_growth", 0)
            self.growth_widget.set_value(f"{growth:+.1f}%")

            enrollment_data = data.get("enrollment_trend", [])
            if enrollment_data:
                self.enrollment_chart.set_data(enrollment_data)
            assessment_data = data.get("assessment_distribution", [])
            if assessment_data:
                self.assessment_chart.set_data(assessment_data)
            age_data = data.get("age_distribution", [])
            if age_data:
                self.age_chart.set_data(age_data)
            score_data = data.get("score_distribution", [])
            if score_data:
                self.score_chart.set_data(score_data)
        except Exception as exc:
            logger.exception("Failed to load analytics data")
            self._feedback.system_error(
                exc,
                message="Student analytics could not be loaded.",
                retry_action_id="student-analytics-refresh",
                key="student-analytics-load",
            )

    def _export_report(self) -> None:
        # Export service is not part of the current Student analytics contract yet.
        self._feedback.info(
            "Analytics report export is not available yet.",
            title="Export unavailable",
            key="student-analytics-export",
        )
