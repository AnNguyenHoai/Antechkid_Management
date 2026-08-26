# -*- coding: utf-8 -*-
"""
ReportListWidget - displays list of generated reports for a student.
"""
import os
import sys
import subprocess
from typing import Optional, List
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame
)

from centermanager.models.report import Report
from centermanager.services.report_service import ReportService
from centermanager.ui.design_system.tokens import COLORS, SPACING


class ReportListWidget(QWidget):
    report_changed = Signal()
    def __init__(self, report_service: ReportService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = report_service
        self._student_id: Optional[int] = None
        self._reports: List[Report] = []
        self._write_enabled = False

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background: transparent;
            }
            QListWidget::item {
                padding: 0px;
            }
        """)
        layout.addWidget(self.list_widget)

    def _show_empty(self):
        self.list_widget.clear()
        empty_item = QListWidgetItem("Chưa có báo cáo nào.")
        empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list_widget.addItem(empty_item)

    def set_student(self, student_id: int):
        self._student_id = student_id
        self._load_reports()

    def _load_reports(self):
        if self._student_id is None:
            self._show_empty()
            return
        try:
            self._reports = self._service.get_student_reports(self._student_id)
            self._update_list()
        except Exception as e:
            self._show_empty()

    def _update_list(self):
        self.list_widget.clear()
        if not self._reports:
            self._show_empty()
            return

        for report in self._reports:
            item = QListWidgetItem()
            widget = self._create_report_item(report)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _create_report_item(self, report: Report) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(SPACING['sm'])

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Report name from file path
        path_parts = report.file_path.split("/")
        filename = path_parts[-1] if path_parts else "Báo cáo"
        name_label = QLabel(filename)
        name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        info_layout.addWidget(name_label)

        # Metadata
        type_map = {"manual": "📄 Thủ công", "automatic": "🤖 Tự động"}
        type_display = type_map.get(report.report_type, report.report_type)
        meta = f"{type_display} | {report.generated_at.strftime('%d/%m/%Y %H:%M')}"
        if report.generated_by:
            meta += f" | {report.generated_by}"
        if report.trigger_event:
            event_map = {
                "progress_50": "50% tiến độ",
                "progress_100": "Hoàn thành",
                "midterm": "Giữa kỳ",
                "final": "Cuối kỳ",
                "monthly": "Hàng tháng",
            }
            meta += f" | {event_map.get(report.trigger_event, report.trigger_event)}"
        meta_label = QLabel(meta)
        meta_label.setStyleSheet(f"font-size: 11px; color: {COLORS['muted']};")
        info_layout.addWidget(meta_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Open button
        open_btn = QPushButton("📂 Mở")
        open_btn.setFixedWidth(70)
        open_btn.clicked.connect(lambda: self._open_report(report.id))
        layout.addWidget(open_btn)

        delete_btn = QPushButton("🗑️ Xóa")
        delete_btn.setFixedWidth(70)
        delete_btn.setEnabled(self._write_enabled)
        delete_btn.clicked.connect(lambda: self._delete_report(report.id))
        layout.addWidget(delete_btn)

        return widget

    def _open_report(self, report_id: int):
        file_path = self._service.get_report_file_path(report_id)
        if file_path is None or not file_path.exists():
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file báo cáo.")
            return
        try:
            if sys.platform == 'win32':
                os.startfile(str(file_path))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(file_path)])
            else:
                subprocess.run(['xdg-open', str(file_path)])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở file: {str(e)}")

    def _delete_report(self, report_id: int):
        if not self._write_enabled:
            QMessageBox.warning(self, "Read mode", "Start Editing before deleting a report.")
            return
        if QMessageBox.question(
            self, "Xác nhận xóa", "Xóa báo cáo này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_report(report_id)
            self._load_reports()
            self.report_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa báo cáo: {e}")

    def set_write_enabled(self, enabled: bool) -> None:
        """Reports list is read-only; keep API consistent with workspace."""
        self._write_enabled = enabled
        if self._student_id is not None:
            self._update_list()
