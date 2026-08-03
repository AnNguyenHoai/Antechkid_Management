# -*- coding: utf-8 -*-
import logging
from datetime import date
from typing import Optional
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QDoubleSpinBox, QPlainTextEdit, QPushButton,
    QHBoxLayout, QMessageBox, QWidget
)

from centermanager.services.expense_service import ExpenseService, ExpenseValidationError

logger = logging.getLogger(__name__)


class ExpenseFormDialog(QDialog):
    def __init__(
        self,
        expense_service: ExpenseService,
        expense_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._service = expense_service
        self._expense_id = expense_id
        self._is_edit = expense_id is not None

        self.setWindowTitle("Edit Expense" if self._is_edit else "Add Expense")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_expense()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Category
        self.category_combo = QComboBox()
        categories = [
            "Teacher Salary", "Office Rent", "Electricity", "Water",
            "Internet", "Equipment", "Marketing", "Office Supply",
            "Maintenance", "Transportation", "Other"
        ]
        self.category_combo.addItems(categories)
        form.addRow("Category *", self.category_combo)

        # Description
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Description of expense")
        self.desc_edit.setMaximumHeight(80)
        form.addRow("Description *", self.desc_edit)

        # Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999.99)
        self.amount_spin.setPrefix("VND ")
        self.amount_spin.setDecimals(0)
        form.addRow("Amount *", self.amount_spin)

        # Payment Method
        self.method_combo = QComboBox()
        self.method_combo.addItems(["","TÀI KHOẢN CÁ NHÂN", "TÀI KHOẢN CÔNG TY"])
        form.addRow("Payment Method *", self.method_combo)

        # Payment Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Payment Date *", self.date_edit)

        # Paid By
        self.paid_by_edit = QLineEdit()
        self.paid_by_edit.setPlaceholderText("Who paid?")
        form.addRow("Paid By", self.paid_by_edit)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["","ĐÃ HOÀN TRẢ", "CHƯA HOÀN TRẢ"])
        form.addRow("Status", self.status_combo)

        # Note
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Optional note")
        self.note_edit.setMaximumHeight(60)
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

    def _load_expense(self):
        try:
            exp = self._service.get_expense(self._expense_id)
            idx = self.category_combo.findText(exp.category)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            self.desc_edit.setPlainText(exp.description)
            self.amount_spin.setValue(exp.amount)
            idx2 = self.method_combo.findText(exp.payment_method)
            if idx2 >= 0:
                self.method_combo.setCurrentIndex(idx2)
            qdate = QDate(exp.payment_date.year, exp.payment_date.month, exp.payment_date.day)
            self.date_edit.setDate(qdate)
            self.paid_by_edit.setText(exp.paid_by or "")
            idx3 = self.status_combo.findText(exp.status)
            if idx3 >= 0:
                self.status_combo.setCurrentIndex(idx3)
            self.note_edit.setPlainText(exp.note or "")
        except Exception as e:
            logger.exception("Load expense error")
            QMessageBox.critical(self, "Error", "Could not load expense")
            self.reject()

    def _save(self):
        category = self.category_combo.currentText()
        description = self.desc_edit.toPlainText().strip()
        amount = self.amount_spin.value()
        payment_method = self.method_combo.currentText()
        payment_date = self.date_edit.date().toPython()
        paid_by = self.paid_by_edit.text().strip() or None
        status = self.status_combo.currentText()
        note = self.note_edit.toPlainText().strip() or None

        try:
            if self._is_edit:
                self._service.update_expense(
                    expense_id=self._expense_id,
                    category=category,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    paid_by=paid_by,
                    status=status,
                    note=note,
                )
            else:
                self._service.create_expense(
                    category=category,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    paid_by=paid_by,
                    status=status,
                    note=note,
                )
            self.accept()
        except ExpenseValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Save expense error")
            QMessageBox.critical(self, "Error", str(e))