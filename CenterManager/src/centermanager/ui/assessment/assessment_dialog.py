# -*- coding: utf-8 -*-
"""
Dialog for adding or editing an assessment.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QPlainTextEdit, QPushButton, QHBoxLayout,
    QMessageBox, QLabel
)

from centermanager.models.assessment import AssessmentType
from centermanager.services.assessment_service import AssessmentService, AssessmentValidationError
from centermanager.ui.assessment.rating_widget import RatingWidget

logger = logging.getLogger(__name__)


class AssessmentDialog(QDialog):
    def __init__(
        self,
        assessment_service: AssessmentService,
        student_id: int,
        assessment_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = assessment_service
        self._student_id = student_id
        self._assessment_id = assessment_id
        self._is_edit = assessment_id is not None

        self.setWindowTitle("Edit Assessment" if self._is_edit else "Add Assessment")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_assessment()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Assessment Date *", self.date_edit)

        # Type
        self.type_combo = QComboBox()
        for t in AssessmentType.choices():
            self.type_combo.addItem(t)
        form.addRow("Assessment Type *", self.type_combo)

        # Score
        self.rating_widget = RatingWidget()
        form.addRow("Overall Score", self.rating_widget)

        # Strengths
        self.strengths_edit = QPlainTextEdit()
        self.strengths_edit.setPlaceholderText("What the student did well...")
        self.strengths_edit.setMaximumHeight(80)
        form.addRow("Strengths *", self.strengths_edit)

        # Improvements
        self.improvements_edit = QPlainTextEdit()
        self.improvements_edit.setPlaceholderText("Areas needing improvement...")
        self.improvements_edit.setMaximumHeight(80)
        form.addRow("Need Improvement *", self.improvements_edit)

        # Next Goal
        self.next_goal_edit = QPlainTextEdit()
        self.next_goal_edit.setPlaceholderText("What should the student focus on next?")
        self.next_goal_edit.setMaximumHeight(80)
        form.addRow("Next Goal *", self.next_goal_edit)

        # Teacher Comment (optional)
        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlaceholderText("Additional comments (optional)")
        self.comment_edit.setMaximumHeight(80)
        form.addRow("Teacher Comment", self.comment_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_assessment(self) -> None:
        try:
            assessment = self._service.get_assessment(self._assessment_id)
            if assessment.assessment_date:
                qdate = QDate(assessment.assessment_date.year, assessment.assessment_date.month, assessment.assessment_date.day)
                self.date_edit.setDate(qdate)
            idx = self.type_combo.findText(assessment.assessment_type or "")
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)
            self.rating_widget.set_value(assessment.overall_score or 0)
            self.strengths_edit.setPlainText(assessment.strengths or "")
            self.improvements_edit.setPlainText(assessment.improvements or "")
            self.next_goal_edit.setPlainText(assessment.next_goal or "")
            self.comment_edit.setPlainText(assessment.teacher_comment or "")
        except Exception as e:
            logger.exception("Error loading assessment")
            QMessageBox.critical(self, "Error", "Could not load assessment data.")
            self.reject()

    def _save(self) -> None:
        assessment_date = self.date_edit.date().toPython()
        assessment_type = self.type_combo.currentText()
        overall_score = self.rating_widget.value()
        strengths = self.strengths_edit.toPlainText().strip()
        improvements = self.improvements_edit.toPlainText().strip()
        next_goal = self.next_goal_edit.toPlainText().strip()
        teacher_comment = self.comment_edit.toPlainText().strip() or None

        try:
            if self._is_edit:
                self._service.update_assessment(
                    assessment_id=self._assessment_id,
                    assessment_date=assessment_date,
                    assessment_type=assessment_type,
                    overall_score=overall_score,
                    strengths=strengths,
                    improvements=improvements,
                    next_goal=next_goal,
                    teacher_comment=teacher_comment,
                )
            else:
                self._service.create_assessment(
                    student_id=self._student_id,
                    assessment_date=assessment_date,
                    assessment_type=assessment_type,
                    strengths=strengths,
                    improvements=improvements,
                    next_goal=next_goal,
                    overall_score=overall_score,
                    teacher_comment=teacher_comment,
                )
            self.accept()
        except AssessmentValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving assessment")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")