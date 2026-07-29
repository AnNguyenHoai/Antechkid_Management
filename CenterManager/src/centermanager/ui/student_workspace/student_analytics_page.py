# -*- coding: utf-8 -*-
"""StudentAnalyticsPage - Analytics focuses on 'How is the business performing over time?'"""
from typing import Optional
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame

from centermanager.services.student_analytics_service import StudentAnalyticsService
from centermanager.ui.shared import ChartCard, MetricCard, SectionHeader
from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.design_system.components import SecondaryButton


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

        # ---- Summary Metrics ----
        self.summary_grid = QHBoxLayout()
        self.summary_grid.setSpacing(SPACING['md'])
        self.avg_score_widget = MetricCard("⭐", "Average Score", "0", "")
        self.total_students_widget = MetricCard("👥", "Total Students", "0", "")
        self.growth_widget = MetricCard("📈", "Monthly Growth", "0%", "")
        self.summary_grid.addWidget(self.avg_score_widget)
        self.summary_grid.addWidget(self.total_students_widget)
        self.summary_grid.addWidget(self.growth_widget)
        container_layout.addLayout(self.summary_grid)

        # ---- Charts Grid (2 columns) ----
        chart_grid = QHBoxLayout()
        chart_grid.setSpacing(SPACING['md'])

        self.enrollment_chart = ChartCard("Enrollment Trend", "bar")
        self.assessment_chart = ChartCard("Assessment Distribution", "pie")
        chart_grid.addWidget(self.enrollment_chart, 1)
        chart_grid.addWidget(self.assessment_chart, 1)
        container_layout.addLayout(chart_grid)

        # ---- Second row ----
        chart_grid2 = QHBoxLayout()
        chart_grid2.setSpacing(SPACING['md'])
        self.age_chart = ChartCard("Age Distribution", "bar")
        self.score_chart = ChartCard("Score Distribution", "bar")
        chart_grid2.addWidget(self.age_chart, 1)
        chart_grid2.addWidget(self.score_chart, 1)
        container_layout.addLayout(chart_grid2)

        # ---- Export button ----
        export_section = QHBoxLayout()
        export_section.addStretch()
        self.export_btn = SecondaryButton("📊 Export Analytics Report")
        self.export_btn.clicked.connect(self._export_report)
        export_section.addWidget(self.export_btn)
        container_layout.addLayout(export_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self):
        try:
            data = self._service.get_dashboard_analytics()
            # Summary metrics
            self.avg_score_widget.set_value(f"{data.get('average_score', 0):.1f}/5")
            self.total_students_widget.set_value(str(data.get('total_students', 0)))
            growth = data.get('monthly_growth', 0)
            self.growth_widget.set_value(f"{growth:+.1f}%")

            # Charts
            enrollment_data = data.get('enrollment_trend', [])
            if enrollment_data:
                self.enrollment_chart.set_data(enrollment_data)

            assessment_data = data.get('assessment_distribution', [])
            if assessment_data:
                self.assessment_chart.set_data(assessment_data)

            age_data = data.get('age_distribution', [])
            if age_data:
                self.age_chart.set_data(age_data)

            score_data = data.get('score_distribution', [])
            if score_data:
                self.score_chart.set_data(score_data)
        except Exception as e:
            import logging
            logging.exception("Failed to load analytics data")

    def _export_report(self):
        # Placeholder: sẽ implement export sau
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Export", "Analytics report export will be available soon.")