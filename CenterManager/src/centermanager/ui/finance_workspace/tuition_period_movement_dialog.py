"""Read-only FinancePeriod tuition movement dialog with CSV export."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QFileDialog, QMessageBox,
)

from centermanager.services.tuition_period_movement_service import (
    TuitionPeriodMovementService,
)


class TuitionPeriodMovementDialog(QDialog):
    HEADERS = (
        "Enrollment", "Học sinh", "Lớp", "Đầu kỳ", "HP phát sinh",
        "Thu thuần", "Điều chỉnh", "Cuối kỳ",
    )
    WIDTHS = (110, 200, 180, 155, 155, 145, 155, 155)

    def __init__(self, outstanding_service, period_start, period_end, *,
                 class_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Biến động công nợ học phí theo kỳ")
        self.resize(1150, 660)
        self.report = TuitionPeriodMovementService(outstanding_service).build(
            period_start=period_start, period_end=period_end, class_id=class_id,
        )
        layout = QVBoxLayout(self)
        title = QLabel(
            f"Kỳ {period_start:%d/%m/%Y} – {period_end:%d/%m/%Y} · "
            "Số dư theo từng Enrollment, không bù trừ giữa các khóa"
        )
        title.setWordWrap(True)
        layout.addWidget(title)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(list(self.HEADERS))
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for i, width in enumerate(self.WIDTHS):
            self.table.setColumnWidth(i, width)
        self.table.setRowCount(len(self.report.rows))
        for row_index, movement in enumerate(self.report.rows):
            values = (
                movement.enrollment_id,
                f"{movement.student_name} ({movement.student_code})",
                movement.class_name,
                self._fmt(movement.opening),
                self._fmt(movement.accrued),
                self._fmt(movement.received),
                self._fmt(movement.adjustments),
                self._fmt(movement.closing),
            )
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.table.setItem(row_index, col_index, item)
        layout.addWidget(self.table, 1)
        total = self.report.totals
        assert total["opening"] + total["accrued"] - total["received"] - total["adjustments"] == total["closing"]
        self.summary = QLabel(
            "TỔNG HỢP CÁC KHÓA ĐÃ CẤU HÌNH: "
            f"Đầu {self._fmt(total['opening'])} + "
            f"Phát sinh {self._fmt(total['accrued'])} − "
            f"Thu thuần {self._fmt(total['received'])} − "
            f"Điều chỉnh {self._fmt(total['adjustments'])} = "
            f"Cuối {self._fmt(total['closing'])}. "
            f"Nợ phải thu {self._fmt(total['receivable'])}; "
            f"Trả trước {self._fmt(total['prepaid'])}."
        )
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.warning = QLabel(
            "Thu thuần gồm các khoản thu và hoàn tiền có dấu. Điều chỉnh gồm "
            "tín dụng và chuyển lớp. "
            f"Khóa chưa cấu hình: {total['unconfigured']} "
            f"(thu {self._fmt(total['unresolved_received'])}, "
            f"điều chỉnh {self._fmt(total['unresolved_adjustments'])}); "
            "không đưa vào tổng công nợ đã xác định."
        )
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)
        controls = QHBoxLayout()
        controls.addStretch()
        export_btn = QPushButton("Xuất CSV biến động")
        export_btn.clicked.connect(self.export_csv)
        controls.addWidget(export_btn)
        close_btn = QPushButton("Đóng")
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)
        layout.addLayout(controls)

    @staticmethod
    def _fmt(value):
        if value is None:
            return "Chưa cấu hình"
        return f"{Decimal(str(value)):,.0f} VND"

    def to_csv(self) -> str:
        target = io.StringIO(newline="")
        writer = csv.writer(target)
        writer.writerow(("Từ ngày", self.report.period_start.isoformat(),
                         "Đến ngày", self.report.period_end.isoformat()))
        writer.writerow(self.HEADERS)
        for item in self.report.rows:
            writer.writerow((
                item.enrollment_id,
                f"{item.student_name} ({item.student_code})",
                item.class_name,
                *(str(value) if value is not None else "UNCONFIGURED" for value in (
                    item.opening, item.accrued, item.received,
                    item.adjustments, item.closing,
                )),
            ))
        writer.writerow(())
        writer.writerow(("Trạng thái", "Chỉ tổng hợp các Enrollment đã cấu hình học phí"))
        for key, value in self.report.totals.items():
            writer.writerow((key, str(value)))
        return target.getvalue()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất biến động học phí", "tuition_period_movement.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            from pathlib import Path
            Path(path).write_text(self.to_csv(), encoding="utf-8-sig")
        except OSError as exc:
            QMessageBox.critical(self, "Không thể xuất CSV", str(exc))
