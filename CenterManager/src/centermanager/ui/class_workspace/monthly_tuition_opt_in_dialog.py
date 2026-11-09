"""Explicit UAT-only Enrollment opt-in into a future monthly tuition plan.

The plan applies to a class, but every historical Enrollment switches
individually after the production-grade backup, WRITE and reconciliation gate.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

from centermanager.platform.backup.backup_service import BackupService
from centermanager.services.monthly_tuition_enrollment_service import (
    MonthlyTuitionEnrollmentService,
)
from centermanager.services.tuition_v1_uat_gate import tuition_v1_uat_enabled


class MonthlyTuitionOptInDialog(QDialog):
    """Manual, one-Enrollment-at-a-time UAT activation; never mass-convert."""

    def __init__(self, class_id: int, session_factory, parent=None) -> None:
        super().__init__(parent)
        if not tuition_v1_uat_enabled():
            raise PermissionError("Tuition Engine V1 UAT mode is disabled")
        self._class_id = int(class_id)
        self._factory = session_factory
        self._service = MonthlyTuitionEnrollmentService(session_factory)
        self._backup_path = None
        self.setWindowTitle("THỬ NGHIỆM · Chuyển học sinh sang học phí tháng")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        warning = QLabel(
            "CHỈ DÙNG DATABASE NHÁP. Không thử với dữ liệu vận hành thật. "
            "Mỗi học sinh cần đối soát và kích hoạt riêng. "
            "Chuyển đổi chỉ có hiệu lực từ đầu tháng tương lai."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        form = QFormLayout()
        self.enrollment = QComboBox(self)
        form.addRow("Học sinh / Enrollment", self.enrollment)
        self.effective_month = QDateEdit(self)
        self.effective_month.setCalendarPopup(True)
        self.effective_month.setDisplayFormat("MM/yyyy")
        future = QDate.currentDate().addMonths(1)
        self.effective_month.setDate(QDate(future.year(), future.month(), 1))
        form.addRow("Bắt đầu từ", self.effective_month)
        layout.addLayout(form)
        self.backup_label = QLabel("Chưa có backup được xác minh.")
        self.backup_label.setWordWrap(True)
        layout.addWidget(self.backup_label)
        bar = QHBoxLayout()
        self.backup_button = QPushButton("Tạo backup SQLCipher", self)
        self.activate_button = QPushButton("Kích hoạt cho học sinh đã chọn", self)
        self.activate_button.setEnabled(False)
        close_button = QPushButton("Đóng", self)
        bar.addWidget(self.backup_button)
        bar.addWidget(self.activate_button)
        bar.addWidget(close_button)
        layout.addLayout(bar)
        self.backup_button.clicked.connect(self._create_backup)
        self.activate_button.clicked.connect(self._activate)
        self.enrollment.currentIndexChanged.connect(self._clear_stale_backup)
        self.effective_month.dateChanged.connect(self._clear_stale_backup)
        close_button.clicked.connect(self.reject)
        self._reload_enrollments()

    def _reload_enrollments(self) -> None:
        self.enrollment.clear()
        for enrollment_id, name, already_monthly in self._service.list_class_enrollments(
            self._class_id
        ):
            state = "đã chuyển" if already_monthly else "chưa chuyển"
            self.enrollment.addItem(
                f"{name} · Enrollment #{enrollment_id} ({state})", enrollment_id,
            )
            if already_monthly:
                self.enrollment.model().item(self.enrollment.count() - 1).setEnabled(False)
        self._clear_stale_backup()

    def _clear_stale_backup(self, *_args) -> None:
        self._backup_path = None
        self.backup_label.setText("Chưa có backup cho thao tác này.")
        self.activate_button.setEnabled(False)

    def _create_backup(self) -> None:
        if self.enrollment.currentData() is None:
            QMessageBox.warning(self, "Chưa chọn học sinh", "Không có Enrollment để chuyển.")
            return
        try:
            result = BackupService().create_backup(label="tuition_v1_uat")
            if not result.success or result.backup_path is None:
                raise RuntimeError(result.error or "Backup SQLCipher không thành công")
            self._backup_path = result.backup_path
        except Exception as exc:
            self._clear_stale_backup()
            QMessageBox.critical(self, "Không thể tạo backup", str(exc))
            return
        self.backup_label.setText(f"Backup vừa tạo: {self._backup_path}")
        self.activate_button.setEnabled(True)

    def _activate(self) -> None:
        if not tuition_v1_uat_enabled() or self._backup_path is None:
            return
        enrollment_id = self.enrollment.currentData()
        if enrollment_id is None:
            return
        start = self.effective_month.date().toPython()
        first = date(start.year, start.month, 1)
        answer = QMessageBox.question(
            self,
            "Xác nhận chuyển học phí tháng trên DB nháp",
            f"Chỉ thực hiện trên DATABASE NHÁP. Kích hoạt Enrollment #{enrollment_id} "
            f"từ {first:%d/%m/%Y}? Các kỳ trước giữ nguyên.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            service = MonthlyTuitionEnrollmentService.from_verified_backup(
                self._factory, backup_path=self._backup_path,
            )
            service.activate_future_month(int(enrollment_id), first)
        except Exception as exc:
            QMessageBox.critical(self, "Không thể chuyển Enrollment", str(exc))
            self._clear_stale_backup()
            return
        QMessageBox.information(
            self, "Đã chuyển đổi", f"Enrollment #{enrollment_id} áp dụng học phí tháng từ {first:%d/%m/%Y}.",
        )
        self._reload_enrollments()
