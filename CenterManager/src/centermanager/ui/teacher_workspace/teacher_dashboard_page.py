# -*- coding: utf-8 -*-
"""
TeacherDashboardPage - Dashboard for Teacher Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QSizePolicy
)

from centermanager.services.teacher_service import TeacherService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.ui.shared import StatisticGrid, SectionHeader
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class TeacherDashboardPage(QWidget):
    def __init__(
        self,
        teacher_service: TeacherService,
        assignment_service: TeacherAssignmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._teacher_service = teacher_service
        self._assignment_service = assignment_service
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

        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        try:
            teachers = self._teacher_service.list_teachers()
            total = len(teachers)
            active = sum(1 for t in teachers if t.status == "ACTIVE")
            # Count total assigned classes across all teachers
            total_assignments = 0
            for t in teachers:
                total_assignments += len(self._assignment_service.get_assigned_classes(t.id))

            self.stats_grid.set_metrics([
                {"icon": "👨‍🏫", "label": "Total Teachers", "value": str(total)},
                {"icon": "✅", "label": "Active Teachers", "value": str(active)},
                {"icon": "📚", "label": "Total Assignments", "value": str(total_assignments)},
            ])

        except Exception as e:
            logger.exception("Failed to refresh teacher dashboard")
            self.stats_grid.set_metrics([
                {"icon": "👨‍🏫", "label": "Total Teachers", "value": "0"},
                {"icon": "✅", "label": "Active Teachers", "value": "0"},
                {"icon": "📚", "label": "Total Assignments", "value": "0"},
            ])