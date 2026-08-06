# -*- coding: utf-8 -*-
"""
Assessment Section for Student Workspace.
Displays latest assessment and history list.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy
)

from centermanager.models.assessment import Assessment
from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.assessment.rating_widget import RatingWidget
from centermanager.ui.assessment.assessment_dialog import AssessmentDialog
from centermanager.ui.assessment.assessment_detail import AssessmentDetailDialog

logger = logging.getLogger(__name__)


class AssessmentSection(QWidget):
    """Section displaying latest assessment and history."""
    assessment_changed = Signal()  # emitted when assessment is added/updated/deleted

    def __init__(self, assessment_service: AssessmentService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = assessment_service
        self._student_id: Optional[int] = None
        self._latest: Optional[Assessment] = None
        self._history: list[Assessment] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header with add button
        header = QHBoxLayout()
        title = QLabel("📊 Assessment")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.add_btn = QPushButton("+ Add Assessment")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Content area (latest + history)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setSpacing(12)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.content)

        # Empty state initially
        self._show_empty()

    def _show_empty(self) -> None:
        self._clear_content()
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)
        icon = QLabel("📊")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        msg = QLabel("No assessments.\nStart tracking student progress.")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet("color: #999; font-size: 14px;")
        empty_layout.addWidget(icon)
        empty_layout.addWidget(msg)
        self.content_layout.addWidget(empty_widget)

    def _clear_content(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_student(self, student_id: int) -> None:
        """Load assessments for the given student."""
        self._student_id = student_id
        self._latest = None
        self._history = []
        self._load_data()

    def _load_data(self) -> None:
        if self._student_id is None:
            return
        try:
            self._latest = self._service.get_latest_assessment(self._student_id)
            self._history = self._service.get_assessments_for_student(self._student_id)
        except Exception as e:
            logger.exception("Error loading assessments")
            self._latest = None
            self._history = []

        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_content()
        if not self._latest and not self._history:
            self._show_empty()
            return

        # Show latest assessment (if exists)
        if self._latest:
            latest_card = self._create_latest_card(self._latest)
            self.content_layout.addWidget(latest_card)

        # Show history (if more than 1 assessment)
        if len(self._history) > 1:
            history_label = QLabel("History")
            history_label.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 8px;")
            self.content_layout.addWidget(history_label)
            for assessment in self._history:
                if assessment.id == self._latest.id:
                    continue  # skip latest, already shown
                history_item = self._create_history_item(assessment)
                self.content_layout.addWidget(history_item)

        self.content_layout.addStretch()

    def _create_latest_card(self, assessment: Assessment) -> QWidget:
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: #fafafa;
                padding: 8px 12px;
            }
        """)
        layout = QVBoxLayout(card)

        # Header: type + date + click to view
        header = QHBoxLayout()
        type_label = QLabel(assessment.assessment_type or "Assessment")
        type_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(type_label)
        date_str = assessment.assessment_date.strftime("%d/%m/%Y") if assessment.assessment_date else ""
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #666; font-size: 12px;")
        header.addWidget(date_label)
        header.addStretch()
        view_btn = QPushButton("View")
        view_btn.setFixedWidth(60)
        view_btn.clicked.connect(lambda: self._on_view(assessment.id))
        header.addWidget(view_btn)
        layout.addLayout(header)

        # Score
        if assessment.overall_score is not None:
            rating = RatingWidget()
            rating.set_value(assessment.overall_score)
            rating.setEnabled(False)
            layout.addWidget(rating)

        # Strengths, improvements, next_goal (shortened)
        if assessment.strengths:
            layout.addWidget(self._create_label("Strengths:", assessment.strengths[:100] + "..." if len(assessment.strengths) > 100 else assessment.strengths))
        if assessment.improvements:
            layout.addWidget(self._create_label("Improvements:", assessment.improvements[:100] + "..." if len(assessment.improvements) > 100 else assessment.improvements))
        if assessment.next_goal:
            layout.addWidget(self._create_label("Next Goal:", assessment.next_goal[:100] + "..." if len(assessment.next_goal) > 100 else assessment.next_goal))

        return card

    def _create_history_item(self, assessment: Assessment) -> QWidget:
        item = QWidget()
        layout = QHBoxLayout(item)
        layout.setContentsMargins(4, 2, 4, 2)
        date_str = assessment.assessment_date.strftime("%d/%m/%Y") if assessment.assessment_date else ""
        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-size: 12px; color: #555;")
        layout.addWidget(date_label)
        type_label = QLabel(assessment.assessment_type or "")
        type_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(type_label)
        if assessment.overall_score is not None:
            stars = "★" * assessment.overall_score + "☆" * (5 - assessment.overall_score)
            score_label = QLabel(stars)
            score_label.setStyleSheet("color: #f5b342; font-size: 12px;")
            layout.addWidget(score_label)
        layout.addStretch()
        view_btn = QPushButton("View")
        view_btn.setFixedWidth(50)
        view_btn.clicked.connect(lambda: self._on_view(assessment.id))
        layout.addWidget(view_btn)
        return item

    def _create_label(self, title: str, text: str) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 2, 0, 2)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 500; font-size: 12px; color: #666;")
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(title_label)
        layout.addWidget(text_label)
        return w

    def _on_add(self) -> None:
        if self._student_id is None:
            return
        dialog = AssessmentDialog(self._service, self._student_id, parent=self)
        if dialog.exec() == AssessmentDialog.DialogCode.Accepted:
            self._load_data()
            self.assessment_changed.emit()

    def _on_view(self, assessment_id: int) -> None:
        dialog = AssessmentDetailDialog(self._service, assessment_id, parent=self)
        if dialog.exec() == AssessmentDetailDialog.DialogCode.Accepted:
            self._load_data()
            self.assessment_changed.emit()

    def refresh(self) -> None:
        if self._student_id is not None:
            self._load_data()
        else:
            self._show_empty()
    def set_write_enabled(self, enabled: bool) -> None:
        """Enable/disable write actions (Add button)."""
        self.add_btn.setEnabled(enabled)
        # Các nút Edit/Delete nằm trong dialog, không cần xử lý ở đây.