# -*- coding: utf-8 -*-
import logging
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton,
    QHBoxLayout, QFrame, QMessageBox
)

from centermanager.services.expense_service import ExpenseService

logger = logging.getLogger(__name__)


class ExpenseDetailDialog(QDialog):
    def __init__(self, expense_service: ExpenseService, expense_id: int, parent=None):
        super().__init__(parent)
        self._service = expense_service
        self._expense_id = expense_id
        self.setWindowTitle("Expense Detail")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.category_label = QLabel()
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        self.amount_label = QLabel()
        self.method_label = QLabel()
        self.date_label = QLabel()
        self.paid_by_label = QLabel()
        self.status_label = QLabel()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)

        form.addRow("Category:", self.category_label)
        form.addRow("Description:", self.desc_label)
        form.addRow("Amount:", self.amount_label)
        form.addRow("Payment Method:", self.method_label)
        form.addRow("Payment Date:", self.date_label)
        form.addRow("Paid By:", self.paid_by_label)
        form.addRow("Status:", self.status_label)
        form.addRow("Note:", self.note_label)

        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _load_data(self):
        try:
            exp = self._service.get_expense(self._expense_id)
            self.category_label.setText(exp.category)
            self.desc_label.setText(exp.description)
            self.amount_label.setText(f"{exp.amount:,.0f} VND")
            self.method_label.setText(exp.payment_method)
            self.date_label.setText(exp.payment_date.strftime("%d/%m/%Y"))
            self.paid_by_label.setText(exp.paid_by or "-")
            self.status_label.setText(exp.status)
            self.note_label.setText(exp.note or "-")
        except Exception as e:
            logger.exception("Load detail error")
            QMessageBox.critical(self, "Error", "Could not load expense")
            self.reject()