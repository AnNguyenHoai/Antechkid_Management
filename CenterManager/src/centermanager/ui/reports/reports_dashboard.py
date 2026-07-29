# -*- coding: utf-8 -*-
"""
ReportsDashboard - KPI cards and charts for Reports Workspace.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame

from centermanager.services.student_service import StudentService
from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.shared import StatisticGrid, EmptyState, SectionHeader
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.models.parent import Parent
from centermanager.models.assessment import Assessment
from sqlalchemy.orm import sessionmaker
from centermanager.database.engine import create_production_engine

logger = logging.getLogger(__name__)


class ReportsDashboard(QWidget):
    def __init__(
        self,
        student_service: StudentService,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._assessment_service = assessment_service
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

        # KPI Stats
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # Placeholder for charts
        header = SectionHeader("Student Analytics")
        container_layout.addWidget(header)

        empty = EmptyState(
            icon="📈",
            title="Charts and Reports",
            description="Visual analytics will be available here."
        )
        container_layout.addWidget(empty)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        try:
            students = self._student_service.list_students()
            total = len(students)
            active = sum(1 for s in students if s.status == "ACTIVE")
            # Assessment stats
            engine = create_production_engine()
            session_factory = sessionmaker(bind=engine)
            with session_factory() as session:
                assessments = session.query(Assessment).all()
                total_assessments = len(assessments)
                # Students with at least one assessment
                student_ids_with_assessment = set(a.student_id for a in assessments)
                completion_rate = (len(student_ids_with_assessment) / total * 100) if total > 0 else 0
                # Missing parents
                from centermanager.models.parent import Parent
                students_with_parent = set()
                parents = session.query(Parent).all()
                for p in parents:
                    students_with_parent.add(p.student_id)
                missing_parents = total - len(students_with_parent)
                # Missing assessments
                missing_assessments = total - len(student_ids_with_assessment)

                self.stats_grid.set_metrics([
                    {"icon": "👥", "label": "Total Students", "value": str(total)},
                    {"icon": "✅", "label": "Active Students", "value": str(active)},
                    {"icon": "📊", "label": "Total Assessments", "value": str(total_assessments)},
                    {"icon": "⭐", "label": "Completion Rate", "value": f"{completion_rate:.1f}%"},
                    {"icon": "⚠️", "label": "Missing Parents", "value": str(missing_parents)},
                    {"icon": "⚠️", "label": "Missing Assessments", "value": str(missing_assessments)},
                ], columns=3)
        except Exception as e:
            logger.exception("Failed to load reports data")