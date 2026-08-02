# -*- coding: utf-8 -*-
"""
IncomeFormDialog - create or edit income.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QDoubleSpinBox, QPushButton, QHBoxLayout,
    QMessageBox, QWidget, QLabel
)

from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.core.current_user import get_current_user

logger = logging.getLogger(__name__)


class IncomeFormDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        income_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._income_id = income_id
        self._is_edit = income_id is not None

        self.setWindowTitle("Edit Income" if self._is_edit else "Add Income")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_income()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Student (combo) - only for create
        self.student_combo = QComboBox()
        self._load_students()
        form.addRow("Student *", self.student_combo)
        if self._is_edit:
            self.student_combo.setEnabled(False)

        # Class (combo) - only for create
        self.class_combo = QComboBox()
        self._load_classes()
        form.addRow("Class *", self.class_combo)
        if self._is_edit:
            self.class_combo.setEnabled(False)

        # Income Type (combo) - only for create
        self.type_combo = QComboBox()
        for t in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(t)
        form.addRow("Income Type *", self.type_combo)
        if self._is_edit:
            self.type_combo.setEnabled(False)

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

        # Payment Period (NEW)
        self.period_combo = QComboBox()
        self.period_combo.addItem("", "")  # empty
        # Tạo danh sách các kỳ: từ tháng 1 đến tháng 12 của năm hiện tại và năm trước
        current_year = date.today().year
        for year in range(current_year - 1, current_year + 1):
            for month in range(1, 13):
                period = f"Tháng {month}/{year}"
                self.period_combo.addItem(period, period)
        form.addRow("Payment Period", self.period_combo)

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
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_students(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_combo.clear()
            for s in students:
                self.student_combo.addItem(f"{s.full_name} ({s.student_code})", s.id)
        except Exception as e:
            logger.exception("Error loading students")

    def _load_classes(self) -> None:
        try:
            classes = self._class_service.list_classes()
            self.class_combo.clear()
            for c in classes:
                self.class_combo.addItem(c.name, c.id)
        except Exception as e:
            logger.exception("Error loading classes")

    def _load_income(self) -> None:
        try:
            income = self._income_service.get_income(self._income_id)
            # Set student
            idx = self.student_combo.findData(income.student_id)
            if idx >= 0:
                self.student_combo.setCurrentIndex(idx)
            # Set class
            idx2 = self.class_combo.findData(income.class_id)
            if idx2 >= 0:
                self.class_combo.setCurrentIndex(idx2)
            # Set type
            idx3 = self.type_combo.findText(income.income_type)
            if idx3 >= 0:
                self.type_combo.setCurrentIndex(idx3)
            self.amount_spin.setValue(income.amount)
            idx4 = self.method_combo.findText(income.payment_method)
            if idx4 >= 0:
                self.method_combo.setCurrentIndex(idx4)
            qdate = QDate(income.payment_date.year, income.payment_date.month, income.payment_date.day)
            self.date_edit.setDate(qdate)
            # Set period
            if income.payment_period:
                idx5 = self.period_combo.findData(income.payment_period)
                if idx5 >= 0:
                    self.period_combo.setCurrentIndex(idx5)
                else:
                    # If not in list, add it
                    self.period_combo.addItem(income.payment_period, income.payment_period)
                    self.period_combo.setCurrentIndex(self.period_combo.count() - 1)
            self.received_by_edit.setText(income.received_by or "")
            self.note_edit.setText(income.note or "")
        except Exception as e:
            logger.exception("Error loading income")
            QMessageBox.critical(self, "Error", "Could not load income data.")
            self.reject()

    def _save(self) -> None:
        student_id = self.student_combo.currentData()
        class_id = self.class_combo.currentData()
        income_type = self.type_combo.currentText()
        amount = self.amount_spin.value()
        payment_method = self.method_combo.currentText()
        payment_date = self.date_edit.date().toPython()
        payment_period = self.period_combo.currentData() or None
        received_by = self.received_by_edit.text().strip() or None
        note = self.note_edit.text().strip() or None

        try:
            if self._is_edit:
                self._income_service.update_income(
                    income_id=self._income_id,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period,
                    note=note,
                )
            else:
                self._income_service.create_income(
                    student_id=student_id,
                    class_id=class_id,
                    amount=amount,
                    income_type=income_type,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period,
                    received_by=received_by,
                    note=note,
                )
            self.accept()
        except IncomeValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving income")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")