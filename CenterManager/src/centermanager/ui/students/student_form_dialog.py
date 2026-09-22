# -*- coding: utf-8 -*-
"""Dialog for creating or editing a student."""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from centermanager.services.student_service import StudentService
from centermanager.services.exceptions import StudentValidationError, StudentNotFoundError
from centermanager.ui.design_system import (
    Button,
    ButtonVariant,
    ComponentSize,
    FormField,
    FormSection,
    Input,
    Select,
)
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)

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

        self.setObjectName("StudentFormDialog")
        self.setWindowTitle("Edit Student" if self._is_edit else "Add Student")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._setup_ui()
        self._connect_signals()

        if self._is_edit:
            self._load_student()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["lg"])

        self.title_label = QLabel("Edit student" if self._is_edit else "Add student")
        self.title_label.setObjectName("StudentFormTitle")
        layout.addWidget(self.title_label)

        self.description_label = QLabel(
            "Update the student profile used across classes, reports, and parent communication."
            if self._is_edit
            else "Create the core student profile. Additional information can be added later."
        )
        self.description_label.setObjectName("StudentFormDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        section = FormSection(
            "Student information",
            "Keep the profile concise and use the preferred name only when needed.",
            parent=self,
        )
        layout.addWidget(section)

        # Full Name (required)
        self.full_name_edit = Input("Enter full name", clearable=True)
        self.full_name_field = section.add_field(
            FormField("Full Name", self.full_name_edit, required=True)
        )

        # Preferred Name
        self.preferred_name_edit = Input("Optional", clearable=True)
        self.preferred_name_field = section.add_field(
            FormField("Preferred Name", self.preferred_name_edit)
        )

        # Date of Birth (nullable)
        self.dob_edit = QDateEdit()
        self.dob_edit.setObjectName("StudentDobInput")
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setDisplayFormat("dd/MM/yyyy")
        self.dob_edit.setSpecialValueText("")
        self.dob_edit.setDate(QDate(2000, 1, 1))
        self.dob_edit.setDateTime(QDate(2000, 1, 1).startOfDay())
        self._update_dob_ui()

        dob_widget = QWidget()
        dob_layout = QHBoxLayout(dob_widget)
        dob_layout.setContentsMargins(0, 0, 0, 0)
        dob_layout.setSpacing(SPACING["sm"])
        dob_layout.addWidget(self.dob_edit, 1)
        self.clear_dob_btn = Button(
            "Clear",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.MEDIUM,
        )
        dob_layout.addWidget(self.clear_dob_btn)
        self.dob_field = section.add_field(FormField("Date of Birth", dob_widget))

        # Gender
        self.gender_combo = Select(["", "Male", "Female", "Other"])
        self.gender_field = section.add_field(FormField("Gender", self.gender_combo))

        # Current Level
        self.level_edit = Input("e.g. Python Beginner", clearable=True)
        self.level_field = section.add_field(FormField("Current Level", self.level_edit))

        # Notes (multiline)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setObjectName("StudentNotesInput")
        self.notes_edit.setPlaceholderText("Additional notes (optional)")
        self.notes_edit.setMaximumHeight(100)
        self.notes_field = section.add_field(FormField("Notes", self.notes_edit))

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(SPACING["sm"])
        btn_layout.addStretch()
        self.cancel_btn = Button("Cancel", variant=ButtonVariant.SECONDARY)
        self.save_btn = Button("Save", variant=ButtonVariant.PRIMARY)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        self.setStyleSheet(
            f"""
            QDialog#StudentFormDialog {{
                background-color: {COLORS["surface_page"]};
            }}
            QLabel#StudentFormTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QLabel#StudentFormDescription {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
            }}
            QDateEdit#StudentDobInput, QPlainTextEdit#StudentNotesInput {{
                background-color: {COLORS["surface_card"]};
                color: {COLORS["text_primary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_strong"]};
                border-radius: {RADIUS["md"]}px;
                padding: {SPACING["sm"]}px {SPACING["md"]}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
            }}
            QDateEdit#StudentDobInput:focus, QPlainTextEdit#StudentNotesInput:focus {{
                border-color: {COLORS["focus_ring"]};
            }}
            """
        )

    def _connect_signals(self) -> None:
        self.dob_edit.dateChanged.connect(self._on_date_changed)
        self.clear_dob_btn.clicked.connect(self._clear_dob)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)
        self.full_name_edit.textChanged.connect(self.full_name_field.clear_error)

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
        except Exception:
            logger.exception("Error loading student")
            QMessageBox.critical(self, "Error", "Could not load student data.")
            self.reject()
            return

        self.full_name_edit.setText(student.full_name)
        self.preferred_name_edit.setText(student.preferred_name or "")

        if student.date_of_birth:
            self._dob_null = False
            qdate = QDate(
                student.date_of_birth.year,
                student.date_of_birth.month,
                student.date_of_birth.day,
            )
            self.dob_edit.setDate(qdate)
        else:
            self._dob_null = True
            self.dob_edit.setDate(QDate(2000, 1, 1))
        self._update_dob_ui()

        gender_index = self.gender_combo.findText(
            student.gender or "", Qt.MatchFlag.MatchFixedString
        )
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
        self.full_name_field.clear_error()

        try:
            if self._is_edit:
                self._service.update_student(
                    student_id=self._student_id,
                    full_name=full_name,
                    preferred_name=preferred_name,
                    date_of_birth=dob,
                    gender=gender,
                    current_level=level,
                    notes=notes,
                )
                logger.info("Updated student %s", self._student_id)
            else:
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
            self.full_name_field.set_error(str(e))
            self.full_name_edit.setFocus()
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception:
            logger.exception("Unexpected error saving student")
            QMessageBox.critical(
                self,
                "Error",
                "An unexpected error occurred. Please check the logs.",
            )
