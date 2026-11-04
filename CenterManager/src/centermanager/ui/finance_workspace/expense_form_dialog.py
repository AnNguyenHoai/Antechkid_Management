# -*- coding: utf-8 -*-
import logging
from datetime import date
from typing import Optional
from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QPlainTextEdit, QPushButton,
    QHBoxLayout, QMessageBox, QWidget, QLabel
)

from centermanager.core.clock import get_clock
from centermanager.core.wallet import WalletMappingError, resolve_wallet
from centermanager.services.expense_service import ExpenseService, ExpenseValidationError
from centermanager.ui.design_system.components import AutoClearDoubleSpinBox
logger = logging.getLogger(__name__)


class ExpenseFormDialog(QDialog):
    def __init__(
        self,
        expense_service: ExpenseService,
        expense_id: Optional[int] = None,
        initial_payment_date: Optional[date] = None,
        parent: Optional[QWidget] = None,
        attachment_service=None,
    ):
        super().__init__(parent)
        self._service = expense_service
        self._expense_id = expense_id
        self._is_edit = expense_id is not None
        self._initial_payment_date = initial_payment_date or get_clock().today()
        self._loaded_category: Optional[str] = None
        self._loaded_description: Optional[str] = None
        # Funding source of the loaded row; None = new expense or legacy row.
        self._loaded_funding: Optional[str] = None
        self._attachment_service = attachment_service
        self.voucher_widget = None

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

        # FEAT-001: company wallets are realized immediately; a personal
        # account is an employee advance ("CHƯA HOÀN TRẢ") until reimbursed.
        self.method_combo = QComboBox()
        self.method_combo.addItem("CASH CÔNG TY", "CASH")
        self.method_combo.addItem("BANK CÔNG TY", "BANK")
        self.method_combo.addItem("TK CÁ NHÂN", "PERSONAL")
        form.addRow("Nguồn chi *", self.method_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        initial = self._initial_payment_date
        self.date_edit.setDate(QDate(initial.year, initial.month, initial.day))
        form.addRow("Payment Date *", self.date_edit)

        self.paid_by_edit = QLineEdit()
        self.paid_by_edit.setPlaceholderText("Who paid?")
        form.addRow("Paid By", self.paid_by_edit)

        # Status is derived from the funding source; it is only editable for
        # legacy rows that the migration could not classify.
        self.status_combo = QComboBox()
        self.status_combo.addItem("ĐÃ CHI / ĐÃ HOÀN TRẢ", "Completed")
        self.status_combo.addItem("CHƯA HOÀN TRẢ", "Pending")
        self.status_combo.setEnabled(False)
        form.addRow("Trạng thái", self.status_combo)

        self.funding_hint = QLabel(self)
        self.funding_hint.setWordWrap(True)
        self.funding_hint.setStyleSheet("color: #536479; font-size: 12px;")
        form.addRow("", self.funding_hint)
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        self._on_method_changed()

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Optional note")
        self.note_edit.setMaximumHeight(60)
        form.addRow("Note", self.note_edit)

        layout.addLayout(form)

        if self._attachment_service is not None:
            # FEAT-004: optional accounting vouchers (D-009).
            from centermanager.ui.finance_workspace.voucher_attachment_widget import VoucherAttachmentWidget
            self.voucher_widget = VoucherAttachmentWidget(
                self._attachment_service, "EXPENSE", self._expense_id, parent=self
            )
            layout.addWidget(self.voucher_widget)

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

    def _on_method_changed(self, *_args) -> None:
        method = self.method_combo.currentData()
        if self._is_edit and self._loaded_funding is None:
            # Legacy/unclassified row (or still loading): keep the stored
            # status selectable and do not derive it from the wallet.
            self.funding_hint.setText(
                "Khoản chi cũ chưa được phân loại nguồn chi; kiểm tra trạng thái trước khi lưu."
            )
            return
        if method == "PERSONAL":
            self._select_status("Pending")
            self.funding_hint.setText(
                "Nhân viên ứng tiền: CHƯA HOÀN TRẢ, chưa tính vào tiền chi của công ty. "
                "Dùng thao tác Hoàn trả ở danh sách Chi khi công ty trả lại tiền."
            )
        elif method in ("CASH", "BANK"):
            self._select_status("Completed")
            self.funding_hint.setText("Chi bằng ví công ty: tính ngay vào tiền chi.")
        else:
            self.funding_hint.setText("")

    def _select_status(self, value: str) -> None:
        index = self.status_combo.findData(value)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)

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
                self.category_combo.addItem(exp.category)
                idx = self.category_combo.count() - 1
            self.category_combo.setCurrentIndex(idx)

            self.desc_edit.setPlainText(exp.description or "")
            self.amount_spin.setValue(exp.amount)
            self._loaded_funding = getattr(exp, "funding_source", None)
            self.status_combo.setEnabled(self._loaded_funding is None)
            try:
                if ExpenseService.is_personal_method(exp.payment_method):
                    idx2 = self.method_combo.findData("PERSONAL")
                else:
                    wallet = resolve_wallet(exp.payment_method).value
                    idx2 = self.method_combo.findData(wallet)
            except WalletMappingError:
                self.method_combo.addItem(
                    f"Legacy value requires selection: {exp.payment_method}",
                    None,
                )
                idx2 = self.method_combo.count() - 1
            if idx2 >= 0:
                self.method_combo.setCurrentIndex(idx2)
            qdate = QDate(exp.payment_date.year, exp.payment_date.month, exp.payment_date.day)
            self.date_edit.setDate(qdate)
            self.paid_by_edit.setText(exp.paid_by or "")
            if self._loaded_funding is not None:
                self._on_method_changed()
            idx3 = self.status_combo.findData(self._canonical_status(exp.status))
            if idx3 >= 0:
                self.status_combo.setCurrentIndex(idx3)
            if self._loaded_funding == "PERSONAL" and exp.status == "Pending":
                # The company wallet is chosen only when reimbursing.
                self.method_combo.setEnabled(False)
            elif self._loaded_funding is not None:
                # A classified row cannot switch between company and personal.
                personal_index = self.method_combo.findData("PERSONAL")
                if personal_index >= 0:
                    self.method_combo.removeItem(personal_index)
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
        if payment_method is None:
            QMessageBox.warning(
                self,
                "Wallet required",
                "Chọn nguồn chi (CASH CÔNG TY, BANK CÔNG TY hoặc TK CÁ NHÂN) trước khi lưu.",
            )
            return
        payment_date = self.date_edit.date().toPython()
        paid_by = self.paid_by_edit.text().strip()
        status = self.status_combo.currentData()
        note = self.note_edit.toPlainText().strip()

        try:
            if self._is_edit:
                category_update = (
                    None if category == self._loaded_category else category
                )
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
                created = self._service.create_expense(
                    category=category,
                    description=description,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    paid_by=paid_by or None,
                    status=status,
                    note=note or None,
                )
                self._commit_vouchers(getattr(created, "id", None))
            self.accept()
        except ExpenseValidationError as exc:
            QMessageBox.warning(self, "Validation Error", str(exc))
        except Exception as exc:
            logger.exception("Save expense error")
            QMessageBox.critical(self, "Error", str(exc))

    def _commit_vouchers(self, expense_id) -> None:
        if self.voucher_widget is None or expense_id is None:
            return
        errors = self.voucher_widget.commit_pending(expense_id)
        if errors:
            QMessageBox.warning(
                self,
                "Chứng từ",
                "Khoản chi đã được lưu nhưng một số chứng từ chưa đính kèm được:\n" + "\n".join(errors),
            )
