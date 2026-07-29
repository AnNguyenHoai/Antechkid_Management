# -*- coding: utf-8 -*-
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame

from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.ui.shared import ChartCard, MetricCard
from centermanager.ui.design_system.tokens import SPACING


class StudentAnalyticsPage(QWidget):
    def __init__(self, analytics_service: StudentAnalyticsService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = analytics_service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(SPACING['xl'])
        container_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])

        # Average Score card
        self.avg_score_widget = MetricCard("⭐", "Average Score", "0", "")
        container_layout.addWidget(self.avg_score_widget)

        # Charts grid
        chart_grid = QHBoxLayout()
        self.enrollment_chart = ChartCard("Enrollment Trend", "bar")
        self.assessment_chart = ChartCard("Assessment Distribution", "pie")
        chart_grid.addWidget(self.enrollment_chart, 1)
        chart_grid.addWidget(self.assessment_chart, 1)
        container_layout.addLayout(chart_grid)

        self.age_chart = ChartCard("Age Distribution", "bar")
        container_layout.addWidget(self.age_chart)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self):
        data = self._service.get_dashboard_analytics()
        self.avg_score_widget.set_value(f"{data['average_score']:.1f}/5")
        self.enrollment_chart.set_data(data['enrollment_trend'])
        self.assessment_chart.set_data(data['assessment_distribution'])
        self.age_chart.set_data(data['age_distribution'])