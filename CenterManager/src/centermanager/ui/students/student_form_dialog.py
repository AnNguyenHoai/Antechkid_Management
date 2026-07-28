# -*- coding: utf-8 -*-
"""
Dialog for creating or editing a student.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QPlainTextEdit, QPushButton, QHBoxLayout,
    QMessageBox, QWidget
)

from centermanager.services.student_service import StudentService
from centermanager.services.exceptions import StudentValidationError, StudentNotFoundError

logger = logging.getLogger(__name__)


class StudentFormDialog(QDialog):
    """Dialog for creating or editing a student."""

    def __init__(
        self,
        student_service: StudentService,
        student_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = student_service
        self._student_id = student_id
        self._is_edit = student_id is not None
        self._dob_null = True
        self._suppress_date_changed = False

        self.setWindowTitle("Edit Student" if self._is_edit else "Add Student")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._connect_signals()

        if self._is_edit:
            self._load_student()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Full Name (required)
        self.full_name_edit = QLineEdit()
        self.full_name_edit.setPlaceholderText("Enter full name")
        form.addRow("Full Name *", self.full_name_edit)

        # Preferred Name
        self.preferred_name_edit = QLineEdit()
        self.preferred_name_edit.setPlaceholderText("Optional")
        form.addRow("Preferred Name", self.preferred_name_edit)

        # Date of Birth (nullable)
        self.dob_edit = QDateEdit()
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setDisplayFormat("dd/MM/yyyy")
        self.dob_edit.setSpecialValueText("")  # empty text when null
        self.dob_edit.setDate(QDate(2000, 1, 1))
        self.dob_edit.setDateTime(QDate(2000, 1, 1).startOfDay())
        self._update_dob_ui()

        dob_widget = QWidget()
        dob_layout = QHBoxLayout(dob_widget)
        dob_layout.setContentsMargins(0, 0, 0, 0)
        dob_layout.setSpacing(4)
        dob_layout.addWidget(self.dob_edit)
        self.clear_dob_btn = QPushButton("Clear")
        self.clear_dob_btn.setFixedWidth(60)
        dob_layout.addWidget(self.clear_dob_btn)
        form.addRow("Date of Birth", dob_widget)

        # Gender
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["", "Male", "Female", "Other"])
        form.addRow("Gender", self.gender_combo)

        # Current Level
        self.level_edit = QLineEdit()
        self.level_edit.setPlaceholderText("e.g. Python Beginner")
        form.addRow("Current Level", self.level_edit)

        # Notes (multiline)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Additional notes (optional)")
        self.notes_edit.setMaximumHeight(100)
        form.addRow("Notes", self.notes_edit)

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

    def _connect_signals(self) -> None:
        self.dob_edit.dateChanged.connect(self._on_date_changed)
        self.clear_dob_btn.clicked.connect(self._clear_dob)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _on_date_changed(self) -> None:
        if self._suppress_date_changed:
            return
        self._dob_null = False
        self._update_dob_ui()

    def _clear_dob(self) -> None:
        self._suppress_date_changed = True
        self._dob_null = True
        self.dob_edit.setDate(QDate(2000, 1, 1))
        self._suppress_date_changed = False
        self._update_dob_ui()

    def _update_dob_ui(self) -> None:
        if self._dob_null:
            self.dob_edit.setSpecialValueText("")
            self.dob_edit.setDate(QDate(2000, 1, 1))
        else:
            # keep current date
            pass

    def _get_dob(self) -> Optional[date]:
        if self._dob_null:
            return None
        qdate = self.dob_edit.date()
        if not qdate.isValid():
            return None
        return date(qdate.year(), qdate.month(), qdate.day())

    def _load_student(self) -> None:
        try:
            student = self._service.get_student(self._student_id)
        except StudentNotFoundError:
            QMessageBox.warning(self, "Not Found", "Student not found.")
            self.reject()
            return
        except Exception as e:
            logger.exception("Error loading student")
            QMessageBox.critical(self, "Error", "Could not load student data.")
            self.reject()
            return

        self.full_name_edit.setText(student.full_name)
        self.preferred_name_edit.setText(student.preferred_name or "")

        if student.date_of_birth:
            self._dob_null = False
            qdate = QDate(student.date_of_birth.year, student.date_of_birth.month, student.date_of_birth.day)
            self.dob_edit.setDate(qdate)
        else:
            self._dob_null = True
            self.dob_edit.setDate(QDate(2000, 1, 1))
        self._update_dob_ui()

        gender_index = self.gender_combo.findText(student.gender or "", Qt.MatchFlag.MatchFixedString)
        if gender_index >= 0:
            self.gender_combo.setCurrentIndex(gender_index)

        self.level_edit.setText(student.current_level or "")
        self.notes_edit.setPlainText(student.notes or "")

    def _save(self) -> None:
        full_name = self.full_name_edit.text().strip()
        preferred_name = self.preferred_name_edit.text().strip() or None
        dob = self._get_dob()
        gender = self.gender_combo.currentText().strip() or None
        level = self.level_edit.text().strip() or None
        notes = self.notes_edit.toPlainText().strip() or None

        try:
            if self._is_edit:
                # Update existing student
                self._service.update_student(
                    student_id=self._student_id,
                    full_name=full_name,
                    preferred_name=preferred_name,
                    date_of_birth=dob,
                    gender=gender,
                    current_level=level,
                    notes=notes,
                    # status not editable in this sprint
                )
                logger.info(f"Updated student {self._student_id}")
            else:
                # Create new student
                self._service.create_student(
                    full_name=full_name,
                    preferred_name=preferred_name,
                    date_of_birth=dob,
                    gender=gender,
                    status="ACTIVE",
                    current_level=level,
                    notes=notes,
                )
                logger.info("Created new student")
            self.accept()
        except StudentValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Unexpected error saving student")
            QMessageBox.critical(self, "Error", "An unexpected error occurred. Please check the logs.")