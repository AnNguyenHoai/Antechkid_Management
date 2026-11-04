# -*- coding: utf-8 -*-
"""Reimburse a personal-account expense from a company wallet (FEAT-001)."""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from centermanager.core.clock import get_clock
from centermanager.services.expense_service import ExpenseService, ExpenseValidationError

logger = logging.getLogger(__name__)


class ExpenseReimburseDialog(QDialog):
    """Choose the company wallet and date used to repay the employee."""

    def __init__(
        self,
        expense_service: ExpenseService,
        expense_id: int,
        amount: float,
        incurred_date: Optional[date] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = expense_service
        self._expense_id = expense_id
        self.setWindowTitle("Hoàn trả khoản chi TK cá nhân")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        info = QLabel(
            f"Công ty trả lại {amount:,.0f} VND cho người ứng tiền. Khoản chi sẽ chuyển sang "
            "ĐÃ HOÀN TRẢ và được tính vào tiền chi của công ty theo ngày hoàn trả.",
            self,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.wallet_combo = QComboBox(self)
        self.wallet_combo.addItem("CASH CÔNG TY", "CASH")
        self.wallet_combo.addItem("BANK CÔNG TY", "BANK")
        form.addRow("Hoàn trả từ ví *", self.wallet_combo)

        today = get_clock().today()
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMaximumDate(QDate(today.year, today.month, today.day))
        if incurred_date is not None:
            self.date_edit.setMinimumDate(QDate(incurred_date.year, incurred_date.month, incurred_date.day))
        self.date_edit.setDate(QDate(today.year, today.month, today.day))
        form.addRow("Ngày hoàn trả *", self.date_edit)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.confirm_btn = QPushButton("Xác nhận hoàn trả", self)
        self.cancel_btn = QPushButton("Hủy", self)
        buttons.addWidget(self.confirm_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)
        self.confirm_btn.clicked.connect(self._confirm)
        self.cancel_btn.clicked.connect(self.reject)

    def _confirm(self) -> None:
        try:
            self._service.reimburse_expense(
                self._expense_id,
                wallet=self.wallet_combo.currentData(),
                reimbursement_date=self.date_edit.date().toPython(),
            )
            self.accept()
        except ExpenseValidationError as exc:
            QMessageBox.warning(self, "Không thể hoàn trả", str(exc))
        except Exception as exc:
            logger.exception("Expense reimbursement failed")
            QMessageBox.critical(self, "Lỗi", str(exc))
