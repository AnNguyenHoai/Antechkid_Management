# -*- coding: utf-8 -*-
"""
ClassDashboardPage - Dashboard for Class Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QSizePolicy
)

from centermanager.services.class_service import ClassService
from centermanager.services.session_service import SessionService
from centermanager.ui.shared import StatisticGrid, SectionHeader, EmptyState
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class ClassDashboardPage(QWidget):
    def __init__(
        self,
        class_service: ClassService,
        session_service: SessionService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._session_service = session_service
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

        # Upcoming sessions section (placeholder)
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
            # Count upcoming sessions from all classes
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

        except Exception as e:
            logger.exception("Failed to refresh class dashboard")
            self.stats_grid.set_metrics([
                {"icon": "📚", "label": "Total Classes", "value": "0"},
                {"icon": "✅", "label": "Active Classes", "value": "0"},
                {"icon": "👨‍🎓", "label": "Total Students", "value": "0"},
                {"icon": "📅", "label": "Upcoming Sessions (7d)", "value": "0"},
            ])
            self.upcoming_label.setText("Unable to load data.")