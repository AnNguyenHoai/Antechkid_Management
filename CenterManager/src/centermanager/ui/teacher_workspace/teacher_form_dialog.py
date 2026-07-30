# -*- coding: utf-8 -*-
"""
TeacherFormDialog - create or edit a teacher.
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

from centermanager.services.teacher_service import TeacherService, TeacherValidationError


logger = logging.getLogger(__name__)


class TeacherFormDialog(QDialog):
    def __init__(
        self,
        teacher_service: TeacherService,
        teacher_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = teacher_service
        self._teacher_id = teacher_id
        self._is_edit = teacher_id is not None

        self.setWindowTitle("Edit Teacher" if self._is_edit else "Add Teacher")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_teacher()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Full Name
        self.full_name_edit = QLineEdit()
        self.full_name_edit.setPlaceholderText("Enter full name")
        form.addRow("Full Name *", self.full_name_edit)

        # Gender
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["", "Male", "Female", "Other"])
        form.addRow("Gender", self.gender_combo)

        # Date of Birth
        self.dob_edit = QDateEdit()
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setDisplayFormat("dd/MM/yyyy")
        self.dob_edit.setSpecialValueText("")
        self.dob_edit.setDate(QDate(2000, 1, 1))
        form.addRow("Date of Birth", self.dob_edit)

        # Phone
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone number")
        form.addRow("Phone", self.phone_edit)

        # Email
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email address")
        form.addRow("Email", self.email_edit)

        # Address
        self.address_edit = QPlainTextEdit()
        self.address_edit.setPlaceholderText("Address (optional)")
        self.address_edit.setMaximumHeight(80)
        form.addRow("Address", self.address_edit)

        # Join Date
        self.join_date_edit = QDateEdit()
        self.join_date_edit.setCalendarPopup(True)
        self.join_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.join_date_edit.setDate(QDate.currentDate())
        form.addRow("Join Date *", self.join_date_edit)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["ACTIVE", "INACTIVE"])
        form.addRow("Status", self.status_combo)

        layout.addLayout(form)

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

    def _load_teacher(self) -> None:
        try:
            teacher = self._service.get_teacher(self._teacher_id)
            self.full_name_edit.setText(teacher.full_name)
            gender_idx = self.gender_combo.findText(teacher.gender or "")
            if gender_idx >= 0:
                self.gender_combo.setCurrentIndex(gender_idx)
            if teacher.date_of_birth:
                qdate = QDate(teacher.date_of_birth.year, teacher.date_of_birth.month, teacher.date_of_birth.day)
                self.dob_edit.setDate(qdate)
            self.phone_edit.setText(teacher.phone or "")
            self.email_edit.setText(teacher.email or "")
            self.address_edit.setPlainText(teacher.address or "")
            if teacher.join_date:
                qdate = QDate(teacher.join_date.year, teacher.join_date.month, teacher.join_date.day)
                self.join_date_edit.setDate(qdate)
            status_idx = self.status_combo.findText(teacher.status or "ACTIVE")
            if status_idx >= 0:
                self.status_combo.setCurrentIndex(status_idx)
        except Exception as e:
            logger.exception("Error loading teacher")
            QMessageBox.critical(self, "Error", "Could not load teacher data.")
            self.reject()

    def _save(self) -> None:
        full_name = self.full_name_edit.text().strip()
        gender = self.gender_combo.currentText().strip() or None
        dob = self.dob_edit.date().toPython() if self.dob_edit.date().isValid() else None
        phone = self.phone_edit.text().strip() or None
        email = self.email_edit.text().strip() or None
        address = self.address_edit.toPlainText().strip() or None
        join_date = self.join_date_edit.date().toPython()
        status = self.status_combo.currentText()

        try:
            if self._is_edit:
                self._service.update_teacher(
                    teacher_id=self._teacher_id,
                    full_name=full_name,
                    gender=gender,
                    date_of_birth=dob,
                    phone=phone,
                    email=email,
                    address=address,
                    join_date=join_date,
                    status=status,
                )
            else:
                self._service.create_teacher(
                    full_name=full_name,
                    gender=gender,
                    date_of_birth=dob,
                    phone=phone,
                    email=email,
                    address=address,
                    join_date=join_date,
                    status=status,
                )
            self.accept()
        except TeacherValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving teacher")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")