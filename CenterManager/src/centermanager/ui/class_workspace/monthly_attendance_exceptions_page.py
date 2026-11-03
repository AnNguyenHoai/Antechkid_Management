"""Monthly attendance exceptions table — read-only operations report."""
from PySide6.QtCore import Qt
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QFileDialog, QMessageBox, QHeaderView,
)
from centermanager.core.clock import get_clock
from centermanager.services.monthly_attendance_exception_service import MonthlyAttendanceExceptionService
from centermanager.ui.shared import DataTable, TableDensity


class MonthlyAttendanceExceptionsPage(QWidget):
    def __init__(self, service: MonthlyAttendanceExceptionService, class_service, parent=None):
        super().__init__(parent)
        self._service = service
        self._classes = class_service
        self._rows = []
        today = get_clock().today()
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(today.year)
        self.month = QSpinBox()
        self.month.setRange(1, 12)
        self.month.setValue(today.month)
        self.class_filter = QComboBox()
        self.class_filter.addItem("Tất cả lớp", None)
        self.issue = QComboBox()
        self.issue.addItem("Tất cả trường hợp", "ALL")
        self.issue.addItem("Tỷ lệ có mặt dưới ngưỡng", "LOW_ATTENDANCE")
        self.issue.addItem("Thiếu ghi nhận điểm danh", "MISSING_RECORDS")
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0, 100)
        self.threshold.setValue(80)
        self.threshold.setSuffix("%")
        for title, widget in (
            ("Năm", self.year), ("Tháng", self.month),
            ("Lớp", self.class_filter), ("Loại", self.issue),
            ("Ngưỡng có mặt", self.threshold),
        ):
            toolbar.addWidget(QLabel(title))
            toolbar.addWidget(widget)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh)
        toolbar.addWidget(refresh)
        export = QPushButton("Xuất CSV")
        export.clicked.connect(self.export_csv)
        toolbar.addWidget(export)
        layout.addLayout(toolbar)
        self.summary = QLabel("Chọn tháng để xem học sinh cần theo dõi.")
        layout.addWidget(self.summary)
        columns = [
            {"key": key, "label": title, "sortable": False}
            for key, title in [
                ("student_code", "Mã HS"), ("student_name", "Học sinh"),
                ("class_name", "Lớp"), ("required", "Buổi phải học"),
                ("present", "Có mặt"), ("absent", "Vắng"),
                ("missing", "Chưa nhập"), ("attendance_rate", "Có mặt %"),
                ("recording_rate", "Đã ghi nhận %"),
            ]
        ]
        self.table = DataTable(columns, page_size=100, density=TableDensity.COMPACT)
        # Nine attendance columns cannot safely fit into a narrow window.
        grid = self.table.table
        grid.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        grid.horizontalHeader().setStretchLastSection(False)
        grid.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        grid.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for index, width in enumerate((110, 190, 175, 125, 90, 85, 105, 115, 135)):
            grid.setColumnWidth(index, width)
        layout.addWidget(self.table)

    def refresh(self):
        try:
            selected = self.class_filter.currentData()
            classes = self._classes.list_classes(include_archived=True)
            previous = self.class_filter.blockSignals(True)
            self.class_filter.clear()
            self.class_filter.addItem("Tất cả lớp", None)
            for cls in classes:
                self.class_filter.addItem(cls.name, cls.id)
            index = self.class_filter.findData(selected)
            self.class_filter.setCurrentIndex(max(0, index))
            self.class_filter.blockSignals(previous)
            self._rows = self._service.list_rows(
                year=self.year.value(), month=self.month.value(),
                class_id=self.class_filter.currentData(),
                minimum_rate=self.threshold.value(), issue=self.issue.currentData(),
            )
            rendered = []
            for row in self._rows:
                rendered.append({
                    **row,
                    "attendance_rate": f'{row["attendance_rate"]:.1f}%',
                    "recording_rate": f'{row["recording_rate"]:.1f}%',
                })
            self.table.set_server_data(rendered, len(rendered), page=1, page_size=max(1, len(rendered)))
            self.summary.setText(
                f'{len(self._rows)} học sinh cần theo dõi · '
                'Có mặt và thiếu ghi nhận là hai chỉ số độc lập.'
            )
        except Exception as exc:
            QMessageBox.critical(self, "Monthly Attendance", str(exc))

    def export_csv(self):
        # Requery without pagination to avoid a stale subset or partial table export.
        try:
            rows = self._service.list_rows(
                year=self.year.value(), month=self.month.value(),
                class_id=self.class_filter.currentData(),
                minimum_rate=self.threshold.value(), issue=self.issue.currentData(),
            )
            filename, _ = QFileDialog.getSaveFileName(
                self, "Xuất Monthly Attendance CSV",
                f'attendance_exceptions_{self.year.value()}_{self.month.value():02d}.csv',
                "CSV (*.csv)",
            )
            if filename:
                path = Path(filename if filename.lower().endswith(".csv") else filename + ".csv")
                path.write_text(self._service.to_csv(rows), encoding="utf-8-sig")
        except Exception as exc:
            QMessageBox.critical(self, "Xuất CSV", str(exc))
