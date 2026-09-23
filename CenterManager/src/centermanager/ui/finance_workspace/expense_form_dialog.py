# -*- coding: utf-8 -*-
import logging
from datetime import date
from typing import Optional
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QPlainTextEdit, QPushButton,
    QHBoxLayout, QMessageBox, QWidget
)

from centermanager.services.expense_service import ExpenseService, ExpenseValidationError
from centermanager.ui.design_system.components import AutoClearDoubleSpinBox
logger = logging.getLogger(__name__)


class ExpenseFormDialog(QDialog):
    def __init__(
        self,
        expense_service: ExpenseService,
        expense_id: Optional[int] = None,
        initial_payment_date: Optional[date] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._service = expense_service
        self._expense_id = expense_id
        self._is_edit = expense_id is not None
        self._initial_payment_date = initial_payment_date or date.today()
        self._loaded_category: Optional[str] = None
        self._loaded_description: Optional[str] = None

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

        self.category_combo = QComboBox()
        categories = [
            "Teacher Salary", "Office Rent", "Electricity", "Water",
            "Internet", "Equipment", "Marketing", "Office Supply",
            "Maintenance", "Transportation", "Other"
        ]
        self.category_combo.addItems(categories)
        form.addRow("Category *", self.category_combo)

        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Description of expense")
        self.desc_edit.setMaximumHeight(80)
        form.addRow("Description *", self.desc_edit)

        self.amount_spin = AutoClearDoubleSpinBox(prefix="VND ")
        self.amount_spin.setRange(0.01, 999999999.99)
        form.addRow("Amount *", self.amount_spin)

        # Display labels are localized; item data is the canonical persisted value.
        self.method_combo = QComboBox()
        self.method_combo.addItem("TÀI KHOẢN CÁ NHÂN", "Cash")
        self.method_combo.addItem("TÀI KHOẢN CÔNG TY", "Bank")
        self.method_combo.addItem("Khác", "Other")
        form.addRow("Payment Method *", self.method_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        initial = self._initial_payment_date
        self.date_edit.setDate(QDate(initial.year, initial.month, initial.day))
        form.addRow("Payment Date *", self.date_edit)

        self.paid_by_edit = QLineEdit()
        self.paid_by_edit.setPlaceholderText("Who paid?")
        form.addRow("Paid By", self.paid_by_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItem("ĐÃ HOÀN TRẢ", "Completed")
        self.status_combo.addItem("CHƯA HOÀN TRẢ", "Pending")
        form.addRow("Status", self.status_combo)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Optional note")
        self.note_edit.setMaximumHeight(60)
        form.addRow("Note", self.note_edit)

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

    @staticmethod
    def _canonical_payment_method(value: str) -> str:
        return {
            "TÀI KHOẢN CÁ NHÂN": "Cash",
            "TÀI KHOẢN CÔNG TY": "Bank",
            "Bank Transfer": "Bank",
        }.get(value, value)

    @staticmethod
    def _canonical_status(value: str) -> str:
        return {
            "ĐÃ HOÀN TRẢ": "Completed",
            "CHƯA HOÀN TRẢ": "Pending",
            "Paid": "Completed",
        }.get(value, value)

    def _load_expense(self):
        try:
            exp = self._service.get_expense(self._expense_id)
            self._loaded_category = exp.category
            self._loaded_description = exp.description

            idx = self.category_combo.findText(exp.category)
            if idx < 0:
                # Preserve unknown legacy categories instead of silently falling
                # back to the first current category on unrelated edits.
                self.category_combo.addItem(exp.category)
                idx = self.category_combo.count() - 1
            self.category_combo.setCurrentIndex(idx)

            # Legacy rows may predate the current required-description contract.
            self.desc_edit.setPlainText(exp.description or "")
            self.amount_spin.setValue(exp.amount)
            idx2 = self.method_combo.findData(
                self._canonical_payment_method(exp.payment_method)
            )
            if idx2 >= 0:
                self.method_combo.setCurrentIndex(idx2)
            qdate = QDate(exp.payment_date.year, exp.payment_date.month, exp.payment_date.day)
            self.date_edit.setDate(qdate)
            self.paid_by_edit.setText(exp.paid_by or "")
            idx3 = self.status_combo.findData(self._canonical_status(exp.status))
            if idx3 >= 0:
                self.status_combo.setCurrentIndex(idx3)
            self.note_edit.setPlainText(exp.note or "")
        except Exception:
            logger.exception("Load expense error")
            QMessageBox.critical(self, "Error", "Could not load expense")
            self.reject()

    def _save(self):
        category = self.category_combo.currentText()
        description = self.desc_edit.toPlainText().strip()
        amount = self.amount_spin.value()
        if amount <= 0:
            QMessageBox.warning(self, "Error", "Amount must be greater than 0.")
            return
        payment_method = self.method_combo.currentData()
        payment_date = self.date_edit.date().toPython()
        # Keep explicit empty strings in edit mode so nullable fields can be
        # cleared instead of being interpreted as "leave unchanged".
        paid_by = self.paid_by_edit.text().strip()
        status = self.status_combo.currentData()
        note = self.note_edit.toPlainText().strip()

        try:
            if self._is_edit:
                # Unknown legacy categories are displayable but are not part of
                # the current validation vocabulary. If unchanged, omit the field
                # so editing another value does not rewrite/reject the legacy row.
                category_update = (
                    None if category == self._loaded_category else category
                )
                # A legacy NULL description must remain editable. Preserve it when
                # the user leaves the empty field untouched; any newly entered text
                # is validated/persisted normally.
                description_update = description
                if self._loaded_description is None and not description:
                    description_update = None

                self._service.update_expense(
                    expense_id=self._expense_id,
                    category=category_update,
                    description=description_update,
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
                    paid_by=paid_by or None,
                    status=status,
                    note=note or None,
                )
            self.accept()
        except ExpenseValidationError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
        except Exception as exc:
            logger.exception("Save expense error")
            QMessageBox.critical(self, "Error", str(exc))
