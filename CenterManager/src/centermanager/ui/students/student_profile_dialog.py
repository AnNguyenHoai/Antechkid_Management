# -*- coding: utf-8 -*-
"""
Basic read-only student profile dialog.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QFrame,
    QMessageBox,
)

from centermanager.services.student_service import StudentService
from centermanager.services.exceptions import StudentNotFoundError
from centermanager.ui.students.helpers import calculate_age, format_date_for_display

logger = logging.getLogger(__name__)


class StudentProfileDialog(QDialog):
    """Read-only profile dialog for a student."""

    def __init__(self, student_service: StudentService, student_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = student_service
        self._student_id = student_id
        self.setWindowTitle("Student Profile")
        self.setMinimumSize(400, 350)
        self.setModal(True)

        self._setup_ui()
        self._load_student()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.form = QFormLayout()
        self.form.setSpacing(6)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.code_label = QLabel()
        self.name_label = QLabel()
        self.preferred_label = QLabel()
        self.dob_label = QLabel()
        self.age_label = QLabel()
        self.gender_label = QLabel()
        self.level_label = QLabel()
        self.status_label = QLabel()
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.notes_label.setTextFormat(Qt.TextFormat.PlainText)

        self.form.addRow("Student Code:", self.code_label)
        self.form.addRow("Full Name:", self.name_label)
        self.form.addRow("Preferred Name:", self.preferred_label)
        self.form.addRow("Date of Birth:", self.dob_label)
        self.form.addRow("Age:", self.age_label)
        self.form.addRow("Gender:", self.gender_label)
        self.form.addRow("Current Level:", self.level_label)
        self.form.addRow("Status:", self.status_label)
        self.form.addRow("Notes:", self.notes_label)

        layout.addLayout(self.form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedWidth(100)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _load_student(self) -> None:
        try:
            student = self._service.get_student(self._student_id)
            self._populate(student)
        except StudentNotFoundError:
            self.code_label.setText("Student not found")
            self.name_label.setText("")
            QMessageBox.warning(self, "Not Found", "Student not found or deleted.")
        except Exception:
            logger.exception("Error loading profile")
            QMessageBox.critical(self, "Error", "An unexpected error occurred. Please check the logs.")

    def _populate(self, student) -> None:
        self.code_label.setText(student.student_code)
        self.name_label.setText(student.full_name)
        self.preferred_label.setText(student.preferred_name or "-")
        self.dob_label.setText(format_date_for_display(student.date_of_birth))
        age = calculate_age(student.date_of_birth)
        self.age_label.setText(str(age) if age is not None else "-")
        self.gender_label.setText(student.gender or "-")
        self.level_label.setText(student.current_level or "-")
        self.status_label.setText(student.status or "-")
        self.notes_label.setText(student.notes or "-")