# -*- coding: utf-8 -*-
import logging
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame
)

from centermanager.services.attendance_service import AttendanceService
from centermanager.models.attendance import Attendance

logger = logging.getLogger(__name__)


class StudentAttendanceWidget(QWidget):
    def __init__(self, attendance_service: AttendanceService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._attendance_service = attendance_service
        self._student_id: Optional[int] = None
        self._setup_ui()
        self._show_empty()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Class", "Session", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.rate_label = QLabel()
        self.rate_label.setStyleSheet("padding: 4px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self.rate_label)

    def _show_empty(self):
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No attendance records"))
        self.table.setSpan(0, 0, 1, 4)
        self.rate_label.setText("Attendance Rate: N/A")
        logger.debug("Attendance widget set to empty state")

    def set_student(self, student_id: int):
        self._student_id = student_id
        self._load_data()

    def _load_data(self):
        if self._student_id is None:
            self._show_empty()
            return
        try:
            attendances = self._attendance_service.get_attendance_for_student(self._student_id)
            logger.info(f"Loaded {len(attendances)} attendance records for student {self._student_id}")
            if not attendances:
                self._show_empty()
                return

            # Xóa span cũ trước khi điền dữ liệu
            self.table.clearSpans()
            self.table.setRowCount(len(attendances))
            for row, att in enumerate(attendances):
                # Date
                date_item = QTableWidgetItem(att.session.scheduled_date.strftime("%d/%m/%Y"))
                self.table.setItem(row, 0, date_item)
                # Class name
                class_name = att.session.class_.name if att.session.class_ else "-"
                class_item = QTableWidgetItem(class_name)
                self.table.setItem(row, 1, class_item)
                # Session
                session_item = QTableWidgetItem(f"#{att.session.session_number} - {att.session.title}")
                self.table.setItem(row, 2, session_item)
                # Status
                status_item = QTableWidgetItem(att.status)
                self.table.setItem(row, 3, status_item)

            # Rate
            rate = self._attendance_service.get_attendance_rate_for_student(self._student_id)
            self.rate_label.setText(f"Attendance Rate: {rate:.1f}%")
            logger.debug(f"Attendance table populated with {len(attendances)} rows")
        except Exception as e:
            logger.exception("Failed to load student attendance")
            self._show_empty()
            # Có thể hiển thị lỗi trên UI nếu cần
            self.rate_label.setText(f"Error: {str(e)}")