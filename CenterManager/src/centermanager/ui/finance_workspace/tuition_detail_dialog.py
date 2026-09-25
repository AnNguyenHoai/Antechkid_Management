# -*- coding: utf-8 -*-
"""Read-only explainable tuition detail dialog."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from centermanager.dto.outstanding_dto import (
    BALANCE_STATE_NO_TUITION_CONFIGURED,
    BALANCE_STATE_OWED,
    BALANCE_STATE_PAID,
    BALANCE_STATE_PREPAID,
)
from centermanager.services.tuition_detail_service import TuitionDetailReadModel


def _money(value: Optional[Decimal]) -> str:
    if value is None:
        return "Chưa cấu hình"
    return f"{value:,.0f} VND"


class TuitionDetailDialog(QDialog):
    """Render a service-owned tuition read model without recalculating money."""

    def __init__(
        self,
        detail: TuitionDetailReadModel,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._detail = detail
        self.setWindowTitle(f"Chi tiết học phí · {detail.student_name}")
        self.resize(980, 720)
        self._setup_ui()

    @staticmethod
    def _balance_label(detail: TuitionDetailReadModel) -> str:
        labels = {
            BALANCE_STATE_OWED: f"Còn nợ {_money(detail.debt_amount)}",
            BALANCE_STATE_PAID: "Đã thanh toán đủ",
            BALANCE_STATE_PREPAID: f"Trả trước / Dư {_money(detail.prepaid_amount)}",
            BALANCE_STATE_NO_TUITION_CONFIGURED: "Chưa cấu hình học phí",
        }
        return labels.get(detail.balance_state, detail.status)

    @staticmethod
    def _readonly_item(value) -> QTableWidgetItem:
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        identity = QLabel(
            f"<b>{self._detail.student_name}</b> ({self._detail.student_code}) · "
            f"{self._detail.class_name} · {self._detail.course_name or '—'} · "
            f"Enrollment #{self._detail.enrollment_id}"
        )
        identity.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(identity)

        summary_box = QGroupBox("Tóm tắt học phí")
        summary = QGridLayout(summary_box)
        contract_range = "—"
        if (
            self._detail.enrolled_from_session is not None
            and self._detail.enrolled_until_session is not None
        ):
            contract_range = (
                f"Buổi {self._detail.enrolled_from_session}–"
                f"{self._detail.enrolled_until_session}"
            )
        values = [
            ("Học phí thỏa thuận", _money(self._detail.agreed_course_fee)),
            ("Số buổi kế hoạch", self._detail.planned_sessions or "Chưa cấu hình"),
            ("Phạm vi Enrollment", contract_range),
            ("Đơn giá / buổi", _money(self._detail.unit_fee)),
            ("Giảm giá hợp đồng", _money(self._detail.contract_discount)),
            ("Đã hoàn thành", self._detail.completed_sessions),
            ("Buổi tính phí", self._detail.billable_sessions),
            ("Phát sinh gộp", _money(self._detail.gross_accrued)),
            ("Giảm giá đã ghi nhận", _money(self._detail.recognized_discount)),
            ("Học phí đã phát sinh", _money(self._detail.net_accrued)),
            ("Đã đóng", _money(self._detail.paid)),
            ("Số dư", self._balance_label(self._detail)),
        ]
        for index, (label, value) in enumerate(values):
            row = index // 3
            column = (index % 3) * 2
            label_widget = QLabel(f"{label}:")
            value_widget = QLabel(str(value))
            if label == "Số dư":
                value_widget.setStyleSheet("font-weight: 600;")
            summary.addWidget(label_widget, row, column)
            summary.addWidget(value_widget, row, column + 1)
        layout.addWidget(summary_box)

        note = QLabel(
            f"Số liệu tại ngày {self._detail.as_of_date:%d/%m/%Y}. "
            "Học phí phát sinh lấy từ TuitionAccrualService; các khoản đã đóng chỉ gồm "
            "Tuition Income ACTIVE được gắn đúng Enrollment."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        tabs = QTabWidget()
        tabs.addTab(self._session_tab(), "Buổi học")
        tabs.addTab(self._payment_tab(), "Lịch sử thanh toán")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _session_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(len(self._detail.sessions), 7)
        table.setHorizontalHeaderLabels(
            ["Buổi", "Ngày", "Trạng thái", "Tiêu đề", "Tính phí", "Đóng góp", "Giải thích"]
        )
        for row, session in enumerate(self._detail.sessions):
            table.setItem(row, 0, self._readonly_item(session.session_number))
            table.setItem(row, 1, self._readonly_item(session.effective_date.strftime("%d/%m/%Y")))
            table.setItem(row, 2, self._readonly_item(session.status))
            table.setItem(row, 3, self._readonly_item(session.title))
            table.setItem(row, 4, self._readonly_item("Có" if session.billable else "Không"))
            table.setItem(row, 5, self._readonly_item(_money(session.billing_contribution)))
            table.setItem(row, 6, self._readonly_item(session.explanation))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table)
        return widget

    def _payment_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        table = QTableWidget(len(self._detail.payments), 6)
        table.setHorizontalHeaderLabels(
            ["Ngày", "Số tiền", "Ví", "Kỳ kế toán", "Tham chiếu", "Ghi chú"]
        )
        for row, payment in enumerate(self._detail.payments):
            table.setItem(row, 0, self._readonly_item(payment.payment_date.strftime("%d/%m/%Y")))
            table.setItem(row, 1, self._readonly_item(_money(payment.amount)))
            table.setItem(row, 2, self._readonly_item(payment.wallet))
            table.setItem(
                row,
                3,
                self._readonly_item(
                    payment.finance_period_start.strftime("%d/%m/%Y")
                    if payment.finance_period_start
                    else "—"
                ),
            )
            table.setItem(row, 4, self._readonly_item(payment.accounting_reference))
            table.setItem(row, 5, self._readonly_item(payment.note or ""))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(table)
        if not self._detail.payments:
            layout.addWidget(QLabel("Chưa có khoản Tuition ACTIVE nào được gắn với Enrollment này."))
        return widget
