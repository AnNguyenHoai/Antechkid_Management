"""Manager-only month tuition plan preview and activation dialog.

This widget is not exposed in the Class Workspace until the V1 rollout flag
passes the Phase 4 release/UAT gate.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDateEdit, QSpinBox,
    QLineEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QMessageBox, QCheckBox,
)

from centermanager.services.monthly_tuition_plan_store import MonthlyTuitionPlanStore
from centermanager.services.monthly_class_schedule_service import MonthlyClassScheduleService
from centermanager.services.tuition_v1_uat_gate import tuition_v1_uat_enabled
from centermanager.ui.class_workspace.monthly_tuition_opt_in_dialog import MonthlyTuitionOptInDialog


class MonthlyTuitionPlanDialog(QDialog):
    def __init__(self, class_id: int, session_factory, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kế hoạch học phí tháng")
        self.setMinimumWidth(540)
        self._class_id = class_id
        self._store = MonthlyTuitionPlanStore(session_factory)
        self._schedule_service = MonthlyClassScheduleService(session_factory)
        self._monthly_settings = self._schedule_service.settings(class_id)
        self._draft_id = None
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.month = QDateEdit(QDate.currentDate().addMonths(1))
        self.month.setCalendarPopup(True)
        self.month.setDisplayFormat("MM/yyyy")
        self.month.setDate(QDate(self.month.date().year(), self.month.date().month(), 1))
        if self._monthly_settings is not None:
            first = self._monthly_settings["effective_month"]
            self.month.setDate(QDate(first.year, first.month, 1))
        self.fee = QSpinBox()
        self.fee.setRange(0, 2_000_000_000)
        self.fee.setSingleStep(50_000)
        self.fee.setValue(
            self._monthly_settings["monthly_fee_vnd"]
            if self._monthly_settings is not None else 800_000
        )
        self.fee.setReadOnly(self._monthly_settings is not None)
        self.fee.setSuffix(" VND")
        self.schedule_version = QLineEdit("manual-v1")
        form.addRow("Tháng áp dụng", self.month)
        form.addRow("Học phí/tháng", self.fee)
        form.addRow("Phiên bản lịch", self.schedule_version)
        root.addLayout(form)
        self.weekday_checkboxes = []
        self.generate_btn = QPushButton("Tạo đủ buổi theo lịch tuần")
        if self._monthly_settings is not None:
            root.addWidget(QLabel("Chọn đúng số thứ học mỗi tuần để tạo toàn bộ lịch gốc"))
            days_row = QHBoxLayout()
            names = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
            existing = self._monthly_settings["weekly_days"]
            suggested = existing or ((5, 6) if self._monthly_settings["sessions_per_week"] == 2 else ())
            for i, name in enumerate(names):
                checkbox = QCheckBox(name)
                checkbox.setChecked(i in suggested)
                checkbox.setEnabled(not bool(existing))
                days_row.addWidget(checkbox)
                self.weekday_checkboxes.append(checkbox)
            root.addLayout(days_row)
            root.addWidget(self.generate_btn)
            self.generate_btn.clicked.connect(self._generate_month_sessions)
        else:
            self.generate_btn.setVisible(False)
        self.notice = QLabel("Xem trước trước khi lưu. Kích hoạt sẽ đóng băng giá từng buổi.")
        self.notice.setWordWrap(True)
        root.addWidget(self.notice)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Session ID", "Lịch gốc", "Phân bổ (VND)"])
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        bar = QHBoxLayout()
        self.preview_btn = QPushButton("Xem trước")
        self.save_btn = QPushButton("Lưu bản nháp")
        self.activate_btn = QPushButton("Kích hoạt")
        self.activate_btn.setEnabled(False)
        self.enrollment_btn = QPushButton("Chuyển học sinh (UAT)")
        self.enrollment_btn.setVisible(tuition_v1_uat_enabled())
        self.close_btn = QPushButton("Đóng")
        for button in (self.preview_btn, self.save_btn, self.activate_btn, self.enrollment_btn, self.close_btn):
            bar.addWidget(button)
        root.addLayout(bar)
        self.preview_btn.clicked.connect(self.preview)
        self.save_btn.clicked.connect(self.save_draft)
        self.activate_btn.clicked.connect(self.activate)
        self.enrollment_btn.clicked.connect(self._open_enrollment_opt_in)
        self.close_btn.clicked.connect(self.reject)
        self.month.dateChanged.connect(self._invalidate_draft)
        self.fee.valueChanged.connect(self._invalidate_draft)
        self.schedule_version.textChanged.connect(self._invalidate_draft)

    def _generate_month_sessions(self):
        if self._monthly_settings is None:
            return
        weekdays = tuple(i for i, checked in enumerate(self.weekday_checkboxes)
                         if checked.isChecked())
        if len(weekdays) != self._monthly_settings["sessions_per_week"]:
            QMessageBox.warning(
                self, "Lịch tuần không hợp lệ",
                f"Chọn đúng {self._monthly_settings['sessions_per_week']} thứ học."
            )
            return
        choice = QMessageBox.question(
            self, "Tạo lịch gốc",
            f"Tạo buổi học tháng {self._month_date():%m/%Y} theo lịch đã chọn? "
            "Các buổi gốc sẽ được dùng để phân bổ học phí. "
            "Không tự tạo điểm danh hoặc Income.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            count = self._schedule_service.create_month_sessions(
                self._class_id, self._month_date(), weekdays
            )
        except Exception as exc:
            QMessageBox.warning(self, "Không thể tạo lịch", str(exc))
            return
        for checked in self.weekday_checkboxes:
            checked.setEnabled(False)
        self.notice.setText(
            f"Đã có đủ {count} buổi. Xem trước, lưu nháp và kích hoạt kế hoạch tháng."
        )
        self.preview()

    def _invalidate_draft(self):
        self._draft_id = None
        self.activate_btn.setEnabled(False)

    def _month_date(self) -> date:
        value = self.month.date()
        return date(value.year(), value.month(), 1)

    def preview(self):
        try:
            rows = self._store.preview(self._class_id, self._month_date(), self.fee.value())
        except Exception as exc:
            QMessageBox.warning(self, "Không thể xem trước", str(exc))
            return
        self.table.setRowCount(len(rows))
        for idx, allocation in enumerate(rows):
            for col, value in enumerate((
                str(allocation.session_id), allocation.scheduled_date.isoformat(),
                f"{allocation.amount_vnd:,}",
            )):
                self.table.setItem(idx, col, QTableWidgetItem(value))
        self.notice.setText(
            f"{len(rows)} buổi · tổng {sum(item.amount_vnd for item in rows):,} VND."
        )

    def save_draft(self):
        try:
            self._draft_id = self._store.create_draft(
                self._class_id, self._month_date(), self.fee.value(),
                self.schedule_version.text(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Không thể lưu", str(exc))
            return
        self.activate_btn.setEnabled(True)
        self.notice.setText(f"Đã lưu bản nháp #{self._draft_id}; chưa kích hoạt.")

    def activate(self):
        if self._draft_id is None:
            return
        accepted = QMessageBox.question(
            self, "Xác nhận kích hoạt",
            "Kích hoạt sẽ giữ nguyên phân bổ học phí của các buổi. Tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if accepted != QMessageBox.StandardButton.Yes:
            return
        try:
            self._store.activate(self._draft_id)
        except Exception as exc:
            QMessageBox.critical(self, "Không thể kích hoạt", str(exc))
            return
        self.activate_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.notice.setText("Đã kích hoạt. Dữ liệu phân bổ là bất biến.")

    def _open_enrollment_opt_in(self):
        if not tuition_v1_uat_enabled():
            return
        MonthlyTuitionOptInDialog(
            self._class_id, self._store._session_factory, parent=self,
        ).exec()
