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
        self.setWindowTitle("Chi tiết thu nhập")
        self.setMinimumWidth(500)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)

        self.source_label = QLabel()
        self.student_label = QLabel()
        self.class_label = QLabel()
        self.type_label = QLabel()
        self.amount_label = QLabel()
        self.method_label = QLabel()
        self.date_label = QLabel()
        self.period_label = QLabel()
        self.received_by_label = QLabel()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)

        form.addRow("Nguồn thu:", self.source_label)
        form.addRow("Học sinh:", self.student_label)
        form.addRow("Lớp học:", self.class_label)
        form.addRow("Loại thu:", self.type_label)
        form.addRow("Số tiền:", self.amount_label)
        form.addRow("Hình thức:", self.method_label)
        form.addRow("Ngày thu:", self.date_label)
        form.addRow("Kỳ thanh toán:", self.period_label)
        form.addRow("Người thu:", self.received_by_label)
        form.addRow("Ghi chú:", self.note_label)

        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Đóng")
        self.close_btn.setFixedWidth(100)
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

    def _load_data(self) -> None:
        try:
            income = self._service.get_income(self._income_id)
            # Source
            if income.student_id is not None:
                self.source_label.setText("Từ học sinh")
                self.student_label.setText(income.student.full_name if income.student else "-")
                self.class_label.setText(income.class_.name if income.class_ else "-")
            else:
                self.source_label.setText("Nguồn khác")
                self.student_label.setText("-")
                self.class_label.setText("-")

            self.type_label.setText(income.income_type)
            self.amount_label.setText(f"{income.amount:,.0f} VND")
            self.method_label.setText(income.payment_method)
            self.date_label.setText(income.payment_date.strftime("%d/%m/%Y"))
            self.period_label.setText(income.payment_period or "-")
            self.received_by_label.setText(income.received_by or "-")
            self.note_label.setText(income.note or "-")
        except Exception as e:
            logger.exception("Error loading income detail")
            QMessageBox.critical(self, "Lỗi", "Không thể tải dữ liệu thu nhập.")
            self.reject()