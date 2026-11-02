"""Read-only student overview for reception and center operations."""
from __future__ import annotations

from datetime import date
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                               QSpinBox, QLineEdit, QPushButton, QMessageBox)
from centermanager.core.clock import get_clock
from centermanager.ui.shared import DataTable, TableDensity


class StudentOverviewPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service
        self._rows = []
        now = get_clock().today()
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(now.year)
        self.month = QSpinBox()
        self.month.setRange(1, 12)
        self.month.setValue(now.month)
        self.status = QComboBox()
        self.status.addItem("Tất cả trạng thái", None)
        self.status.addItem("Đang hoạt động", "ACTIVE")
        self.status.addItem("Archived", "ARCHIVED")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Tìm mã hoặc tên học sinh")
        for label, control in (("Năm", self.year), ("Tháng", self.month), ("Trạng thái", self.status)):
            bar.addWidget(QLabel(label))
            bar.addWidget(control)
        bar.addWidget(self.search)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        layout.addLayout(bar)
        self.summary = QLabel("Tổng quan học sinh")
        layout.addWidget(self.summary)
        columns = [
            {"key": key, "label": title, "sortable": False} for key, title in (
                ("student_code", "Mã HS"), ("student_name", "Học sinh"),
                ("status", "Trạng thái"), ("classes", "Lớp đang học"),
                ("monthly_classes", "Lớp có buổi trong tháng"),
                ("due", "Buổi cần học"), ("present", "Có mặt"),
                ("absent", "Vắng"), ("missing", "Chưa nhập"),
                ("attendance_rate", "Có mặt %"), ("debt", "Còn nợ (VND)"),
            )
        ]
        self.table = DataTable(columns, page_size=50, density=TableDensity.COMPACT)
        layout.addWidget(self.table)
        for control in (self.year, self.month):
            control.valueChanged.connect(self.refresh)
        self.status.currentIndexChanged.connect(self._render)
        self.search.textChanged.connect(self._render)

    def refresh(self, *_args):
        try:
            self._rows = self._service.list_rows(year=self.year.value(), month=self.month.value())
            self._render()
        except Exception as exc:
            QMessageBox.critical(self, "Student Overview", str(exc))

    def _render(self, *_args):
        keyword = self.search.text().strip().casefold()
        status = self.status.currentData()
        rows = [
            row for row in self._rows
            if (not keyword or keyword in (row["student_code"] or "").casefold()
                or keyword in (row["student_name"] or "").casefold())
            and (status is None or row["status"] == status)
        ]
        rendered = [
            {
                **row,
                "attendance_rate": "—" if row["attendance_rate"] is None
                    else f'{row["attendance_rate"]:.1f}%',
                "debt": f'{row["debt"]:,}',
            }
            for row in rows
        ]
        self.table.set_server_data(rendered, len(rendered), page=1, page_size=max(1, len(rendered)))
        self.summary.setText(
            f'{len(rows)} học sinh · {sum(row["missing"] for row in rows)} lượt chưa nhập · '
            f'{sum(row["debt"] for row in rows):,} VND công nợ'
        )
