# -*- coding: utf-8 -*-
"""
AssessmentListPage - List all assessments with search and filter.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame, QLabel,
    QPushButton, QHBoxLayout, QSizePolicy
)

from centermanager.models.assessment import Assessment
from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.shared import EmptyState, SearchToolbar, SectionHeader
from centermanager.ui.assessment.assessment_detail import AssessmentDetailDialog
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class AssessmentListItem(QFrame):
    def __init__(self, assessment: Assessment, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._assessment = assessment
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border-bottom: 1px solid {COLORS['border_light']};
                padding: {SPACING['sm']}px {SPACING['md']}px;
            }}
            QFrame:hover {{
                background: {COLORS['surface_hover']};
            }}
        """)
        self.setFixedHeight(60)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['xs'], SPACING['sm'], SPACING['xs'])
        layout.setSpacing(SPACING['md'])

        # Student info
        student_text = f"{self._assessment.student.full_name} ({self._assessment.student.student_code})" if self._assessment.student else "Unknown"
        student_label = QLabel(student_text)
        student_label.setStyleSheet(f"font-weight: 500; color: {COLORS['text_primary']};")
        layout.addWidget(student_label)

        # Type
        type_label = QLabel(self._assessment.assessment_type or "-")
        type_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        layout.addWidget(type_label)

        # Score
        score_str = "★" * (self._assessment.overall_score or 0) + "☆" * (5 - (self._assessment.overall_score or 0))
        score_label = QLabel(score_str)
        score_label.setStyleSheet(f"color: #f5b342; font-size: 14px;")
        layout.addWidget(score_label)

        layout.addStretch()

        # Date
        date_str = self._assessment.assessment_date.strftime("%d/%m/%Y") if self._assessment.assessment_date else ""
        date_label = QLabel(date_str)
        date_label.setStyleSheet(f"color: {COLORS['muted_light']}; font-size: 12px;")
        layout.addWidget(date_label)

        # View button
        view_btn = QPushButton("View")
        view_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark']};
            }}
        """)
        view_btn.clicked.connect(lambda: self.parent()._on_view(self._assessment.id))
        layout.addWidget(view_btn)

    def assessment_id(self) -> int:
        return self._assessment.id


class AssessmentListPage(QWidget):
    assessment_selected = Signal(int)
    data_updated = Signal()

    def __init__(
        self,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = assessment_service
        self._assessments: List[Assessment] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: white; padding: {SPACING['sm']}px {SPACING['md']}px; border-bottom: 1px solid {COLORS['border_light']};")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['xs'])

        self.search_toolbar = SearchToolbar(
            placeholder="Search by student name or code...",
            filters=[
                {"name": "type", "options": ["Monthly", "Quarterly", "Final", "Custom"]},
            ]
        )
        self.search_toolbar.search_changed.connect(self._filter)
        self.search_toolbar.filter_changed.connect(self._apply_filters)
        toolbar_layout.addWidget(self.search_toolbar)

        layout.addWidget(toolbar)

        # Count label
        self.count_label = QLabel("0 assessments")
        self.count_label.setStyleSheet(f"padding: {SPACING['xs']}px {SPACING['md']}px; font-size: 12px; color: {COLORS['muted']};")
        layout.addWidget(self.count_label)

        # List container
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def refresh(self) -> None:
        try:
            # Use the new method that loads student eagerly
            self._assessments = self._service.get_all_assessments_with_student()
        except Exception as e:
            logger.exception("Failed to load assessments")
            self._assessments = []
        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_container()
        self.count_label.setText(f"{len(self._assessments)} assessments")

        if not self._assessments:
            empty = EmptyState(
                icon="📊",
                title="No assessments yet",
                description="Assessments will appear here as they are created."
            )
            self.container_layout.addWidget(empty)
            return

        for assessment in self._assessments:
            item = AssessmentListItem(assessment)
            self.container_layout.addWidget(item)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _filter(self, text: str) -> None:
        # Simple filter by student name/code
        if not text.strip():
            self._update_ui()
            return
        lower = text.strip().lower()
        filtered = [
            a for a in self._assessments
            if a.student and (lower in a.student.full_name.lower() or lower in a.student.student_code.lower())
        ]
        self._filtered = filtered
        self._update_filtered_ui()

    def _apply_filters(self, filters: dict) -> None:
        # In real implementation, apply filters
        self._update_ui()

    def _update_filtered_ui(self) -> None:
        self._clear_container()
        self.count_label.setText(f"{len(self._filtered)} assessments")

        if not self._filtered:
            empty = EmptyState(
                icon="🔍",
                title="No matching assessments",
                description="Try adjusting your search or filters."
            )
            self.container_layout.addWidget(empty)
            return

        for assessment in self._filtered:
            item = AssessmentListItem(assessment)
            self.container_layout.addWidget(item)
        self.container_layout.addStretch()

    def _on_view(self, assessment_id: int) -> None:
        dialog = AssessmentDetailDialog(self._service, assessment_id, parent=self)
        if dialog.exec() == AssessmentDetailDialog.DialogCode.Accepted:
            self.refresh()
            self.data_updated.emit()