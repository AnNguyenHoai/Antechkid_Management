# -*- coding: utf-8 -*-
"""
StudentFilterDialog - advanced filter dialog.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSpinBox, QLineEdit, QPushButton,
    QLabel, QMessageBox
)

from centermanager.dto.student_filter_dto import StudentFilter


class StudentFilterDialog(QDialog):
    """Dialog to define advanced filters."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setMinimumWidth(350)
        self.setModal(True)

        self._setup_ui()
        self._result: Optional[StudentFilter] = None

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(8)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["All", "Active", "Archived"])
        form.addRow("Status", self.status_combo)

        # Age range
        age_layout = QHBoxLayout()
        self.age_min_spin = QSpinBox()
        self.age_min_spin.setRange(0, 100)
        self.age_min_spin.setSpecialValueText("Any")
        self.age_max_spin = QSpinBox()
        self.age_max_spin.setRange(0, 100)
        self.age_max_spin.setSpecialValueText("Any")
        age_layout.addWidget(QLabel("From"))
        age_layout.addWidget(self.age_min_spin)
        age_layout.addWidget(QLabel("to"))
        age_layout.addWidget(self.age_max_spin)
        form.addRow("Age", age_layout)

        # Enrollment status
        self.enrollment_combo = QComboBox()
        self.enrollment_combo.addItems(["All", "Enrolled", "Not Enrolled"])
        form.addRow("Enrollment", self.enrollment_combo)

        # Assessment status
        self.assessment_combo = QComboBox()
        self.assessment_combo.addItems(["All", "Has Assessment", "No Assessment"])
        form.addRow("Assessment", self.assessment_combo)

        # Class name
        self.class_edit = QLineEdit()
        self.class_edit.setPlaceholderText("Class name (exact match)")
        form.addRow("Class", self.class_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._apply)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

    def _clear(self) -> None:
        self.status_combo.setCurrentIndex(0)
        self.age_min_spin.setValue(0)
        self.age_max_spin.setValue(0)
        self.enrollment_combo.setCurrentIndex(0)
        self.assessment_combo.setCurrentIndex(0)
        self.class_edit.clear()

    def _apply(self) -> None:
        status = None
        if self.status_combo.currentIndex() == 1:
            status = "ACTIVE"
        elif self.status_combo.currentIndex() == 2:
            status = "ARCHIVED"

        age_min = self.age_min_spin.value() or None
        age_max = self.age_max_spin.value() or None
        if age_min == 0:
            age_min = None
        if age_max == 0:
            age_max = None

        enrollment = None
        if self.enrollment_combo.currentIndex() == 1:
            enrollment = "enrolled"
        elif self.enrollment_combo.currentIndex() == 2:
            enrollment = "not_enrolled"

        assessment = None
        if self.assessment_combo.currentIndex() == 1:
            assessment = "has_assessment"
        elif self.assessment_combo.currentIndex() == 2:
            assessment = "no_assessment"

        class_name = self.class_edit.text().strip() or None

        self._result = StudentFilter(
            status=status,
            age_min=age_min,
            age_max=age_max,
            enrollment_status=enrollment,
            assessment_status=assessment,
            class_name=class_name
        )
        self.accept()

    def get_filter(self) -> Optional[StudentFilter]:
        return self._result