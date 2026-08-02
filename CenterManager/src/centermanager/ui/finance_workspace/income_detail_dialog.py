# -*- coding: utf-8 -*-
"""
IncomeDetailDialog - view income details (read-only).
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QPushButton,
    QHBoxLayout, QFrame, QMessageBox
)

from centermanager.services.income_service import IncomeService

logger = logging.getLogger(__name__)


class IncomeDetailDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        income_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = income_service
        self._income_id = income_id
        self.setWindowTitle("Income Detail")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.student_label = QLabel()
        self.class_label = QLabel()
        self.type_label = QLabel()
        self.amount_label = QLabel()
        self.method_label = QLabel()
        self.date_label = QLabel()
        self.period_label = QLabel()   # NEW
        self.received_by_label = QLabel()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)

        form.addRow("Student:", self.student_label)
        form.addRow("Class:", self.class_label)
        form.addRow("Income Type:", self.type_label)
        form.addRow("Amount:", self.amount_label)
        form.addRow("Payment Method:", self.method_label)
        form.addRow("Payment Date:", self.date_label)
        form.addRow("Payment Period:", self.period_label)
        form.addRow("Received By:", self.received_by_label)
        form.addRow("Note:", self.note_label)

        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedWidth(100)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _load_data(self) -> None:
        try:
            income = self._service.get_income(self._income_id)
            self.student_label.setText(income.student.full_name if income.student else "-")
            self.class_label.setText(income.class_.name if income.class_ else "-")
            self.type_label.setText(income.income_type)
            self.amount_label.setText(f"{income.amount:,.0f} VND")
            self.method_label.setText(income.payment_method)
            self.date_label.setText(income.payment_date.strftime("%d/%m/%Y"))
            self.period_label.setText(income.payment_period or "-")
            self.received_by_label.setText(income.received_by or "-")
            self.note_label.setText(income.note or "-")
        except Exception as e:
            logger.exception("Error loading income detail")
            QMessageBox.critical(self, "Error", "Could not load income data.")
            self.reject()