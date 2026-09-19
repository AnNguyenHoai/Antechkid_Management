# -*- coding: utf-8 -*-
"""
StudentFinancialWidget - read-only student finance summary and payment history.

Finance owns money. This widget consumes canonical Finance read APIs only:
OutstandingService for tuition totals and IncomeService for payment history.
Both reads are constrained to the same canonical Finance period.
"""
import logging
from datetime import date
from typing import List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
)

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.models.income import Income
from centermanager.dto.outstanding_dto import StudentOutstandingSummary
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
        parent: Optional[QWidget] = None,
        finance_period_service: Optional[FinancePeriodService] = None,
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
        self._requested_period_start: Optional[date] = None
        self._requested_on_date: Optional[date] = None
        self._resolved_period_start: Optional[date] = None
        self._resolved_period_end: Optional[date] = None

        # Keep existing composition roots stable while allowing the canonical
        # period service to be injected explicitly by newer callers/tests.
        self._finance_period_service = finance_period_service
        if self._finance_period_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                self._finance_period_service = FinancePeriodService(session_factory)

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['md'])

        self.period_label = QLabel("Kỳ tài chính: --")
        self.period_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 12px;"
        )
        layout.addWidget(self.period_label)

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
        self.detail_table.setColumnCount(5)
        self.detail_table.setHorizontalHeaderLabels([
            "Lớp", "Học phí dự kiến", "Đã đóng", "Còn nợ", "Trạng thái"
        ])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.setMaximumHeight(150)
        layout.addWidget(self.detail_table)

        # Open Finance button: navigation only; Student never mutates payments.
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
        try:
            can_open_finance = self._permission_service.has_permission("finance.view")
            self.open_finance_btn.setVisible(bool(can_open_finance))
        except Exception:
            logger.exception("Failed to evaluate finance workspace visibility")
            self.open_finance_btn.setVisible(False)
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
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No payment records"))
        self.table.setSpan(0, 0, 1, 6)
        self.table.setVisible(True)
        self.detail_table.clearSpans()
        self.detail_table.setRowCount(1)
        self.detail_table.setItem(0, 0, QTableWidgetItem("No class enrollment"))
        self.detail_table.setSpan(0, 0, 1, 5)
        self.detail_table.setVisible(True)
        self.total_expected_label.setVisible(False)
        self.total_paid_label.setVisible(False)
        self.outstanding_label.setVisible(False)
        self.status_label.setVisible(False)

    def _show_data(self) -> None:
        self.total_expected_label.setVisible(True)
        self.total_paid_label.setVisible(True)
        self.outstanding_label.setVisible(True)
        self.status_label.setVisible(True)

    def set_finance_period(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> None:
        """Set an optional canonical Finance-period context for this read view."""
        self._requested_period_start = period_start
        self._requested_on_date = on_date
        if self._student_id is not None:
            self.set_student(self._student_id)

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        # Finance data is protected independently from the Student Workspace.
        if not self._can_view_finance():
            self._incomes = []
            self._summary = None
            self._resolved_period_start = None
            self._resolved_period_end = None
            self._update_period_label()
            self._show_empty()
            return

        target_date, period_start, period_end = self._resolve_finance_period_context()
        self._resolved_period_start = period_start
        self._resolved_period_end = period_end
        self._update_period_label()
        self._load_outstanding_summary(period_start, target_date)
        self._load_incomes(period_start, period_end)
        self._update_ui()

    def _can_view_finance(self) -> bool:
        try:
            return bool(self._permission_service.has_permission("finance.view"))
        except Exception:
            logger.exception("Failed to evaluate finance data permission")
            return False

    def _resolve_finance_period_context(
        self,
    ) -> Tuple[date, Optional[date], Optional[date]]:
        """Resolve one canonical period shared by summary and payment history."""
        target_date = self._requested_on_date or self._requested_period_start or date.today()
        if self._finance_period_service is None:
            return target_date, self._requested_period_start, None

        try:
            lookup_date = self._requested_period_start or target_date
            config = self._finance_period_service.get_active_period(lookup_date)
            if config is None:
                return target_date, None, None
            period_start, period_end = self._finance_period_service.get_period_bounds(
                config.effective_from,
                lookup_date,
                config.duration_months,
            )
            return target_date, period_start, period_end
        except Exception:
            logger.exception("Failed to resolve Finance period for student financial view")
            return target_date, self._requested_period_start, None

    def _update_period_label(self) -> None:
        if self._resolved_period_start is None:
            self.period_label.setText("Kỳ tài chính: Chưa cấu hình")
            return
        if self._resolved_period_end is None:
            self.period_label.setText(
                f"Kỳ tài chính: từ {self._resolved_period_start:%d/%m/%Y}"
            )
            return
        self.period_label.setText(
            "Kỳ tài chính: "
            f"{self._resolved_period_start:%d/%m/%Y} - "
            f"{self._resolved_period_end:%d/%m/%Y}"
        )

    def _load_incomes(
        self,
        period_start: Optional[date],
        period_end: Optional[date],
    ) -> None:
        if (
            self._student_id is None
            or not self._can_view_finance()
            or period_start is None
        ):
            self._incomes = []
            return
        try:
            # Ask for one row first to obtain the exact server count, then fetch
            # that count so payment history is never capped by a fixed page size.
            first_page, total = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=1,
                finance_period_start=period_start,
                date_from=period_start,
                date_to=period_end,
                status=Income.STATUS_ACTIVE,
                sort_by="payment_date",
                ascending=False,
            )
            if total <= 1:
                self._incomes = first_page
                return
            items, _ = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=total,
                finance_period_start=period_start,
                date_from=period_start,
                date_to=period_end,
                status=Income.STATUS_ACTIVE,
                sort_by="payment_date",
                ascending=False,
            )
            self._incomes = items
        except Exception:
            logger.exception("Failed to load incomes for student")
            self._incomes = []

    def _load_outstanding_summary(
        self,
        period_start: Optional[date],
        target_date: date,
    ) -> None:
        if self._student_id is None or not self._can_view_finance():
            self._summary = None
            return
        try:
            self._summary = self._outstanding_service.get_student_summary(
                self._student_id,
                period_start=period_start,
                on_date=target_date,
            )
            if self._summary:
                logger.info(
                    "Loaded outstanding summary for student %s: expected=%s, paid=%s",
                    self._student_id,
                    self._summary.total_expected,
                    self._summary.total_paid,
                )
        except Exception:
            logger.exception("Failed to load outstanding summary")
            self._summary = None

    def _update_ui(self) -> None:
        has_summary_data = bool(
            self._summary
            and (
                self._summary.details
                or self._summary.total_expected != 0
                or self._summary.total_paid != 0
            )
        )
        if not self._incomes and not has_summary_data:
            self._show_empty()
            return

        self._show_data()
        self._update_summary()
        self._update_detail_table()
        self._update_payment_history()

    def _update_summary(self) -> None:
        if self._summary is None:
            self.total_expected_label._value_widget.setText("Chưa có dữ liệu")
            self.total_paid_label._value_widget.setText("Chưa có dữ liệu")
            self.outstanding_label._value_widget.setText("Chưa có dữ liệu")
            self.status_label._value_widget.setText("Chưa có lớp học hoặc học phí")
            return

        self.total_paid_label._value_widget.setText(f"{self._summary.total_paid:,.0f} VND")
        has_unconfigured = bool(self._summary.has_unconfigured_tuition)
        if has_unconfigured and self._summary.total_expected == 0:
            self.total_expected_label._value_widget.setText("Chưa xác định")
            self.outstanding_label._value_widget.setText("Chưa xác định")
            self.outstanding_label._value_widget.setStyleSheet(
                "color: #ff9800; font-weight: bold;"
            )
            self.status_label._value_widget.setText("Chưa cấu hình học phí")
            return

        self.total_expected_label._value_widget.setText(
            f"{self._summary.total_expected:,.0f} VND"
        )
        outstanding = self._summary.total_outstanding
        self.outstanding_label._value_widget.setText(f"{outstanding:,.0f} VND")
        if has_unconfigured:
            color = "#ff9800"
            status_text = "Có lớp chưa cấu hình"
        elif outstanding > 0:
            color = "#d32f2f"
            status_text = "Còn nợ"
        elif outstanding == 0:
            color = "#4caf50"
            status_text = "Đã đóng"
        else:
            color = "#ff9800"
            status_text = "Đã đóng quá"
        self.outstanding_label._value_widget.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self.status_label._value_widget.setText(status_text)

    def _update_detail_table(self) -> None:
        self.detail_table.clearSpans()
        if self._summary and self._summary.details:
            self.detail_table.setRowCount(len(self._summary.details))
            for row, detail in enumerate(self._summary.details):
                self.detail_table.setItem(row, 0, QTableWidgetItem(detail.class_name))
                if detail.tuition_configured:
                    expected_text = f"{detail.expected_tuition:,.0f}"
                    outstanding_text = f"{detail.outstanding:,.0f}"
                    status_text = detail.status
                else:
                    expected_text = "Chưa cấu hình"
                    outstanding_text = "Chưa xác định"
                    status_text = "Chưa cấu hình"
                self.detail_table.setItem(row, 1, QTableWidgetItem(expected_text))
                self.detail_table.setItem(row, 2, QTableWidgetItem(f"{detail.paid:,.0f}"))
                self.detail_table.setItem(row, 3, QTableWidgetItem(outstanding_text))
                self.detail_table.setItem(row, 4, QTableWidgetItem(status_text))
            self.detail_table.setVisible(True)
        else:
            self.detail_table.setRowCount(1)
            self.detail_table.setItem(0, 0, QTableWidgetItem("Không có lớp học"))
            self.detail_table.setSpan(0, 0, 1, 5)
            self.detail_table.setVisible(True)

    def _update_payment_history(self) -> None:
        self.table.clearSpans()
        if not self._incomes:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("No payment records"))
            self.table.setSpan(0, 0, 1, 6)
            self.table.setVisible(True)
            return

        self.table.setRowCount(len(self._incomes))
        self.table.setVisible(True)
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
