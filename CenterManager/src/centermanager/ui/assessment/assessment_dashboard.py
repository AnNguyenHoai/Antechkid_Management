# -*- coding: utf-8 -*-
"""
AssessmentDashboard - Dashboard for Assessment Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame

from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.shared import StatisticGrid, EmptyState, SectionHeader
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class AssessmentDashboard(QWidget):
    def __init__(
        self,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = assessment_service
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

        # Stats Grid
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # Placeholder for future charts / lists
        header = SectionHeader("Assessment Overview")
        container_layout.addWidget(header)

        empty = EmptyState(
            icon="📊",
            title="Assessment Analytics",
            description="Charts and detailed statistics will appear here."
        )
        container_layout.addWidget(empty)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        # In a real implementation, fetch stats from service
        # For now, set placeholder stats
        self.stats_grid.set_metrics([
            {"icon": "📊", "label": "Total Assessments", "value": "0"},
            {"icon": "⭐", "label": "Average Score", "value": "0/5"},
            {"icon": "✅", "label": "Completion Rate", "value": "0%"},
            {"icon": "⏳", "label": "Pending Assessments", "value": "0"},
        ])