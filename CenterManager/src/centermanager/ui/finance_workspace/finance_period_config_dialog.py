# -*- coding: utf-8 -*-
"""Minimal admin UI for the existing effective-dated FinancePeriod contract."""
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit, QSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
)


class FinancePeriodConfigDialog(QDialog):
    """Configure effective-dated FinancePeriod rules without inventing new states."""

    def __init__(self, finance_period_service, collaboration_manager=None,
                 notification_service=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = finance_period_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._periods = []
        self.setWindowTitle("Finance Period Configuration")
        self.resize(720, 420)
        self._setup_ui()
        self._reload()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Finance Period dùng cấu hình theo ngày hiệu lực. Thay đổi kỳ bằng cách "
            "tạo cấu hình mới từ ngày hiệu lực; lịch sử cũ được giữ nguyên."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QHBoxLayout()
        form.addWidget(QLabel("Hiệu lực từ:"))
        self.effective_from = QDateEdit()
        self.effective_from.setCalendarPopup(True)
        self.effective_from.setDisplayFormat("dd/MM/yyyy")
        self.effective_from.setDate(QDate.currentDate())
        form.addWidget(self.effective_from)
        form.addWidget(QLabel("Độ dài kỳ:"))
        self.duration = QSpinBox()
        self.duration.setRange(1, 24)
        self.duration.setValue(1)
        self.duration.setSuffix(" tháng")
        form.addWidget(self.duration)
        self.configure_btn = QPushButton("Áp dụng cấu hình mới")
        self.configure_btn.clicked.connect(self._configure)
        form.addWidget(self.configure_btn)
        layout.addLayout(form)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Hiệu lực từ", "Hiệu lực đến", "Độ dài", "Trạng thái"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.deactivate_btn = QPushButton("Kết thúc cấu hình đã chọn")
        self.deactivate_btn.clicked.connect(self._deactivate)
        actions.addWidget(self.deactivate_btn)
        actions.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

    def _ensure_write(self) -> bool:
        if self._collaboration_manager is None:
            return True
        if self._collaboration_manager.ensure_write():
            return True
        self._notify("You must be in WRITE mode to manage Finance Period.", "warning")
        return False

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(self._notification_service, "notify"):
            self._notification_service.notify(message, level)

    def _reload(self) -> None:
        try:
            self._periods = self._service.list_period_configurations()
            self.table.setRowCount(len(self._periods))
            for row, period in enumerate(self._periods):
                values = [
                    str(period.id),
                    period.effective_from.strftime("%d/%m/%Y"),
                    period.effective_to.strftime("%d/%m/%Y") if period.effective_to else "-",
                    f"{period.duration_months} tháng",
                    period.status,
                ]
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
        except Exception as exc:
            QMessageBox.critical(self, "Finance Period", str(exc))

    def _configure(self) -> None:
        if not self._ensure_write():
            return
        try:
            qdate = self.effective_from.date()
            self._service.configure(
                duration_months=self.duration.value(),
                effective_from=date(qdate.year(), qdate.month(), qdate.day()),
            )
            self._notify("Finance Period configuration updated.", "success")
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Không thể cấu hình Finance Period", str(exc))

    def _selected_period(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._periods):
            return None
        return self._periods[row]

    def _deactivate(self) -> None:
        if not self._ensure_write():
            return
        period = self._selected_period()
        if period is None:
            QMessageBox.information(self, "Finance Period", "Hãy chọn một cấu hình.")
            return
        if QMessageBox.question(
            self,
            "Kết thúc Finance Period configuration",
            "Kết thúc cấu hình đã chọn tại ngày hôm nay?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.deactivate(period.id, effective_to=date.today())
            self._notify("Finance Period configuration deactivated.", "success")
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Không thể kết thúc Finance Period", str(exc))
