# -*- coding: utf-8 -*-
"""
Assessment detail dialog (read-only with Edit/Delete buttons).
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton,
    QHBoxLayout, QMessageBox
)

from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.assessment.rating_widget import RatingWidget

logger = logging.getLogger(__name__)


class AssessmentDetailDialog(QDialog):
    def __init__(
        self,
        assessment_service: AssessmentService,
        assessment_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = assessment_service
        self._assessment_id = assessment_id
        self.setWindowTitle("Assessment Details")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Fields (read-only)
        self.form = QFormLayout()
        self.form.setSpacing(8)

        self.date_label = QLabel()
        self.type_label = QLabel()
        self.rating_widget = RatingWidget()
        self.rating_widget.setEnabled(False)
        self.strengths_label = QLabel()
        self.strengths_label.setWordWrap(True)
        self.improvements_label = QLabel()
        self.improvements_label.setWordWrap(True)
        self.next_goal_label = QLabel()
        self.next_goal_label.setWordWrap(True)
        self.comment_label = QLabel()
        self.comment_label.setWordWrap(True)

        self.form.addRow("Date:", self.date_label)
        self.form.addRow("Type:", self.type_label)
        self.form.addRow("Score:", self.rating_widget)
        self.form.addRow("Strengths:", self.strengths_label)
        self.form.addRow("Improvements:", self.improvements_label)
        self.form.addRow("Next Goal:", self.next_goal_label)
        self.form.addRow("Comment:", self.comment_label)

        layout.addLayout(self.form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.edit_btn = QPushButton("Edit")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("color: #d32f2f;")
        self.close_btn = QPushButton("Close")
        btn_layout.addStretch()
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.edit_btn.clicked.connect(self._on_edit)
        self.delete_btn.clicked.connect(self._on_delete)
        self.close_btn.clicked.connect(self.accept)

    def _load_data(self) -> None:
        try:
            assessment = self._service.get_assessment(self._assessment_id)
            self.date_label.setText(assessment.assessment_date.strftime("%d/%m/%Y") if assessment.assessment_date else "-")
            self.type_label.setText(assessment.assessment_type or "-")
            self.rating_widget.set_value(assessment.overall_score or 0)
            self.strengths_label.setText(assessment.strengths or "-")
            self.improvements_label.setText(assessment.improvements or "-")
            self.next_goal_label.setText(assessment.next_goal or "-")
            self.comment_label.setText(assessment.teacher_comment or "-")
        except Exception as e:
            logger.exception("Error loading assessment")
            QMessageBox.critical(self, "Error", "Could not load assessment data.")
            self.reject()

    def _on_edit(self) -> None:
        from centermanager.ui.assessment.assessment_dialog import AssessmentDialog
        dialog = AssessmentDialog(
            self._service,
            student_id=0,  # not needed for edit
            assessment_id=self._assessment_id,
            parent=self
        )
        if dialog.exec() == AssessmentDialog.DialogCode.Accepted:
            self._load_data()
            # Notify parent to refresh workspace (via signal later)
            self.accept()  # close detail, workspace will refresh

    def _on_delete(self) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this assessment?\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_assessment(self._assessment_id)
                QMessageBox.information(self, "Deleted", "Assessment deleted successfully.")
                self.accept()  # close detail, workspace will refresh
            except Exception as e:
                logger.exception("Error deleting assessment")
                QMessageBox.critical(self, "Error", "Could not delete assessment.")