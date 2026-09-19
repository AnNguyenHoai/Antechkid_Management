# -*- coding: utf-8 -*-
"""Read-only Income detail dialog."""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.income import Income
from centermanager.services.income_service import IncomeService

logger = logging.getLogger(__name__)


class IncomeDetailDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        income_id: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = income_service
        self._income_id = income_id
        self.setWindowTitle("Chi tiết thu nhập")
        self.setMinimumWidth(520)
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
        self.payment_period_label = QLabel()
        self.finance_period_label = QLabel()
        self.received_by_label = QLabel()
        self.status_label = QLabel()
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.created_label = QLabel()
        self.updated_label = QLabel()
        self.voided_at_label = QLabel()
        self.voided_by_label = QLabel()
        self.void_reason_label = QLabel()
        self.void_reason_label.setWordWrap(True)

        form.addRow("Nguồn thu:", self.source_label)
        form.addRow("Học sinh:", self.student_label)
        form.addRow("Lớp học:", self.class_label)
        form.addRow("Loại thu:", self.type_label)
        form.addRow("Số tiền:", self.amount_label)
        form.addRow("Hình thức:", self.method_label)
        form.addRow("Ngày thu:", self.date_label)
        form.addRow("Kỳ thanh toán (ghi chú):", self.payment_period_label)
        form.addRow("Finance Period:", self.finance_period_label)
        form.addRow("Người thu:", self.received_by_label)
        form.addRow("Trạng thái:", self.status_label)
        form.addRow("Ghi chú:", self.note_label)
        form.addRow("Tạo lúc:", self.created_label)
        form.addRow("Cập nhật lúc:", self.updated_label)
        form.addRow("Void lúc:", self.voided_at_label)
        form.addRow("Void bởi:", self.voided_by_label)
        form.addRow("Lý do void:", self.void_reason_label)
        layout.addLayout(form)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    @staticmethod
    def _format_datetime(value) -> str:
        return value.strftime("%d/%m/%Y %H:%M:%S") if value else "-"

    def _load_data(self) -> None:
        try:
            income = self._service.get_income(self._income_id)
            linked = income.student_id is not None
            self.source_label.setText(
                "STUDENT_PAYMENT" if linked else "OTHER_INCOME"
            )
            self.student_label.setText(
                income.student.full_name if linked and income.student else "-"
            )
            self.class_label.setText(
                income.class_.name if linked and income.class_ else "-"
            )
            self.type_label.setText(income.income_type)
            self.amount_label.setText(f"{income.amount:,.0f} VND")
            self.method_label.setText(income.payment_method)
            self.date_label.setText(
                income.payment_date.strftime("%d/%m/%Y")
            )
            self.payment_period_label.setText(income.payment_period or "-")
            self.finance_period_label.setText(
                income.finance_period_start.strftime("%d/%m/%Y")
                if income.finance_period_start
                else "-"
            )
            self.received_by_label.setText(income.received_by or "-")
            self.status_label.setText(income.status)
            self.note_label.setText(income.note or "-")
            self.created_label.setText(
                self._format_datetime(getattr(income, "created_at", None))
            )
            self.updated_label.setText(
                self._format_datetime(getattr(income, "updated_at", None))
            )

            is_voided = income.status == Income.STATUS_VOIDED
            self.voided_at_label.setText(
                self._format_datetime(income.voided_at)
            )
            self.voided_by_label.setText(income.voided_by or "-")
            self.void_reason_label.setText(income.void_reason or "-")
            for widget in (
                self.voided_at_label,
                self.voided_by_label,
                self.void_reason_label,
            ):
                widget.setVisible(is_voided)
            # QFormLayout labels remain visible; keep explicit "-" values when active
            # so the dialog is deterministic even across Qt versions.
        except Exception:
            logger.exception("Error loading income detail")
            QMessageBox.critical(
                self, "Lỗi", "Không thể tải dữ liệu thu nhập."
            )
            self.reject()
