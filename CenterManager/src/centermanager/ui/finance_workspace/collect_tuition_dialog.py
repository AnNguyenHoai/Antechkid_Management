# -*- coding: utf-8 -*-
"""
CollectTuitionDialog - dialog for collecting tuition from student detail.
"""
import logging
from typing import Optional
from datetime import date

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QDoubleSpinBox, QPushButton, QHBoxLayout,
    QMessageBox, QLabel, QWidget
)

from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user

logger = logging.getLogger(__name__)


class CollectTuitionDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        permission_service: PermissionService,
        student_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._permission_service = permission_service
        self._student_id = student_id

        self.setWindowTitle("Collect Tuition")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()
        self._load_student_info()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Student (read-only)
        self.student_label = QLabel()
        self.student_label.setStyleSheet("font-weight: bold;")
        form.addRow("Student:", self.student_label)

        # Class (auto-filter enrolled classes)
        self.class_combo = QComboBox()
        self._load_classes()
        form.addRow("Class *", self.class_combo)

        # Income Type
        self.type_combo = QComboBox()
        for t in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(t)
        self.type_combo.setCurrentText("Tuition")
        form.addRow("Income Type *", self.type_combo)

        # Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999.99)
        self.amount_spin.setPrefix("VND ")
        self.amount_spin.setDecimals(0)
        form.addRow("Amount *", self.amount_spin)

        # Payment Method
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Cash", "Bank Transfer"])
        form.addRow("Payment Method *", self.method_combo)

        # Payment Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Payment Date *", self.date_edit)

        # Received By (auto-filled)
        self.received_by_edit = QLineEdit()
        current_user = get_current_user()
        if current_user:
            self.received_by_edit.setText(current_user.full_name)
        self.received_by_edit.setPlaceholderText("Received by")
        form.addRow("Received By", self.received_by_edit)

        # Note
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Optional note")
        form.addRow("Note", self.note_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.collect_btn = QPushButton("💰 Collect")
        self.collect_btn.setFixedWidth(120)
        self.collect_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1565c0;
            }
        """)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.collect_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.collect_btn.clicked.connect(self._collect)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_student_info(self) -> None:
        try:
            student = self._student_service.get_student(self._student_id)
            self.student_label.setText(f"{student.full_name} ({student.student_code})")
        except Exception as e:
            logger.exception("Error loading student")
            QMessageBox.critical(self, "Error", "Could not load student data.")
            self.reject()

    def _load_classes(self) -> None:
        """Load classes that the student is enrolled in."""
        try:
            # Get all classes
            classes = self._class_service.list_classes()
            self.class_combo.clear()
            # TODO: Filter only enrolled classes for this student
            # For now, show all classes
            for c in classes:
                self.class_combo.addItem(c.name, c.id)
        except Exception as e:
            logger.exception("Error loading classes")

    def _collect(self) -> None:
        class_id = self.class_combo.currentData()
        income_type = self.type_combo.currentText()
        amount = self.amount_spin.value()
        payment_method = self.method_combo.currentText()
        payment_date = self.date_edit.date().toPython()
        received_by = self.received_by_edit.text().strip() or None
        note = self.note_edit.text().strip() or None

        if not class_id:
            QMessageBox.warning(self, "Validation Error", "Please select a class.")
            return

        try:
            self._income_service.create_income(
                student_id=self._student_id,
                class_id=class_id,
                amount=amount,
                income_type=income_type,
                payment_method=payment_method,
                payment_date=payment_date,
                received_by=received_by,
                note=note,
            )
            QMessageBox.information(self, "Success", "Tuition collected successfully!")
            self.accept()
        except IncomeValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error collecting tuition")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")