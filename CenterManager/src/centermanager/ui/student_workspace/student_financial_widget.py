# -*- coding: utf-8 -*-
"""
StudentFinancialWidget - displays financial summary and payment history for a student.
Now uses real data from OutstandingService, supports multi-class, and is read-only.
"""
import logging
from typing import Optional, List
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QSizePolicy, QScrollArea
)

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.models.income import Income
from centermanager.dto.outstanding_dto import StudentOutstandingSummary, OutstandingDTO
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY

logger = logging.getLogger(__name__)


class StudentFinancialWidget(QWidget):
    financial_updated = Signal()
    open_finance_clicked = Signal()  # Signal to switch to Finance Workspace

    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        permission_service: PermissionService,
        outstanding_service: OutstandingService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._permission_service = permission_service
        self._outstanding_service = outstanding_service
        self._student_id: Optional[int] = None
        self._incomes: List[Income] = []
        self._summary: Optional[StudentOutstandingSummary] = None

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['md'])

        # Summary cards
        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(SPACING['md'])

        self.total_expected_label = self._create_summary_card("Học phí dự kiến", "0 VND")
        summary_layout.addWidget(self.total_expected_label)

        self.total_paid_label = self._create_summary_card("Đã đóng", "0 VND")
        summary_layout.addWidget(self.total_paid_label)

        self.outstanding_label = self._create_summary_card("Còn nợ", "0 VND")
        summary_layout.addWidget(self.outstanding_label)

        self.status_label = self._create_summary_card("Trạng thái", "Chưa có dữ liệu")
        summary_layout.addWidget(self.status_label)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        # Detail table for each class (multi-class)
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(4)
        self.detail_table.setHorizontalHeaderLabels(["Lớp", "Học phí dự kiến", "Đã đóng", "Còn nợ"])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.setMaximumHeight(150)
        layout.addWidget(self.detail_table)

        # Open Finance button (replaces Collect Tuition)
        btn_layout = QHBoxLayout()
        self.open_finance_btn = QPushButton("💰 Mở Finance Workspace")
        self.open_finance_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark']};
            }}
            QPushButton:disabled {{
                background: {COLORS['muted']};
            }}
        """)
        self.open_finance_btn.setFixedHeight(40)
        self.open_finance_btn.clicked.connect(self.open_finance_clicked.emit)
        btn_layout.addStretch()
        btn_layout.addWidget(self.open_finance_btn)
        layout.addLayout(btn_layout)

        # Payment history table
        history_label = QLabel("Lịch sử thanh toán")
        history_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['section_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
            margin-top: {SPACING['sm']}px;
        """)
        layout.addWidget(history_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Ngày", "Lớp", "Loại", "Số tiền", "Hình thức", "Người thu"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Check permission (only to show/hide button? But we keep button always visible)
        # No need to disable because we removed collect tuition.

    def _create_summary_card(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: {SPACING['md']}px;
                min-width: 120px;
            }}
        """)
        layout = QVBoxLayout(card)
        label_w = QLabel(label)
        label_w.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        value_w = QLabel(value)
        value_w.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(label_w)
        layout.addWidget(value_w)
        card._value_widget = value_w
        return card

    def _show_empty(self) -> None:
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No payment records"))
        self.table.setSpan(0, 0, 1, 6)
        self.detail_table.setRowCount(1)
        self.detail_table.setItem(0, 0, QTableWidgetItem("No class enrollment"))
        self.detail_table.setSpan(0, 0, 1, 4)
        self.total_expected_label.setVisible(False)
        self.total_paid_label.setVisible(False)
        self.outstanding_label.setVisible(False)
        self.status_label.setVisible(False)

    def _show_data(self) -> None:
        self.total_expected_label.setVisible(True)
        self.total_paid_label.setVisible(True)
        self.outstanding_label.setVisible(True)
        self.status_label.setVisible(True)

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self._load_incomes()
        self._load_outstanding_summary()
        self._update_ui()

    def _load_incomes(self) -> None:
        if self._student_id is None:
            self._incomes = []
            return
        try:
            items, total = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=1000
            )
            self._incomes = items
        except Exception as e:
            logger.exception("Failed to load incomes for student")
            self._incomes = []

    def _load_outstanding_summary(self) -> None:
        if self._student_id is None:
            self._summary = None
            return
        try:
            self._summary = self._outstanding_service.get_student_summary(self._student_id)
            if self._summary:
                logger.info(f"Loaded outstanding summary for student {self._student_id}: "
                            f"expected={self._summary.total_expected}, paid={self._summary.total_paid}")
        except Exception as e:
            logger.exception("Failed to load outstanding summary")
            self._summary = None

    def _update_ui(self) -> None:
        if not self._incomes and (self._summary is None or self._summary.total_expected == 0):
            self._show_empty()
            return

        self._show_data()
        self._update_summary()
        self._update_detail_table()
        self._update_payment_history()

    def _update_summary(self) -> None:
        if self._summary and (self._summary.total_expected > 0 or self._summary.total_paid > 0):
            self.total_expected_label._value_widget.setText(f"{self._summary.total_expected:,.0f} VND")
            self.total_paid_label._value_widget.setText(f"{self._summary.total_paid:,.0f} VND")
            outstanding = self._summary.total_outstanding
            if outstanding > 0:
                color = "#d32f2f"
                status_text = "Còn nợ"
            elif outstanding == 0:
                color = "#4caf50"
                status_text = "Đã đóng"
            else:
                color = "#ff9800"
                status_text = "Đã đóng quá"
            self.outstanding_label._value_widget.setText(f"{outstanding:,.0f} VND")
            self.outstanding_label._value_widget.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.status_label._value_widget.setText(status_text)
        else:
            # Hiển thị thông báo không có dữ liệu
            self.total_expected_label._value_widget.setText("Chưa có dữ liệu")
            self.total_expected_label._value_widget.setStyleSheet("color: #999;")
            self.total_paid_label._value_widget.setText("Chưa có dữ liệu")
            self.total_paid_label._value_widget.setStyleSheet("color: #999;")
            self.outstanding_label._value_widget.setText("Chưa có dữ liệu")
            self.outstanding_label._value_widget.setStyleSheet("color: #999;")
            self.status_label._value_widget.setText("Chưa có lớp học hoặc học phí")
            self.status_label._value_widget.setStyleSheet("color: #999;")
            self._show_data()

    def _update_detail_table(self) -> None:
        self.detail_table.clearSpans()
        if self._summary and self._summary.details:
            self.detail_table.setRowCount(len(self._summary.details))
            for row, detail in enumerate(self._summary.details):
                self.detail_table.setItem(row, 0, QTableWidgetItem(detail.class_name))
                self.detail_table.setItem(row, 1, QTableWidgetItem(f"{detail.expected_tuition:,.0f}"))
                self.detail_table.setItem(row, 2, QTableWidgetItem(f"{detail.paid:,.0f}"))
                self.detail_table.setItem(row, 3, QTableWidgetItem(f"{detail.outstanding:,.0f}"))
            self.detail_table.setVisible(True)
        else:
            self.detail_table.setRowCount(1)
            self.detail_table.setItem(0, 0, QTableWidgetItem("Không có lớp học"))
            self.detail_table.setSpan(0, 0, 1, 4)

    def _update_payment_history(self) -> None:
        self.table.clearSpans()
        self.table.setRowCount(len(self._incomes))
        self.table.setVisible(len(self._incomes) > 0)

        for row, income in enumerate(self._incomes):
            self.table.setItem(row, 0, QTableWidgetItem(income.payment_date.strftime("%d/%m/%Y")))
            class_name = income.class_.name if income.class_ else "-"
            self.table.setItem(row, 1, QTableWidgetItem(class_name))
            self.table.setItem(row, 2, QTableWidgetItem(income.income_type))
            self.table.setItem(row, 3, QTableWidgetItem(f"{income.amount:,.0f}"))
            self.table.setItem(row, 4, QTableWidgetItem(income.payment_method))
            self.table.setItem(row, 5, QTableWidgetItem(income.received_by or "-"))

    def refresh(self) -> None:
        if self._student_id is not None:
            self.set_student(self._student_id)
# detail.status
#  "Chưa cấu hình"