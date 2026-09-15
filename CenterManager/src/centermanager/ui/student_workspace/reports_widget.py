# -*- coding: utf-8 -*-
"""
ReportsWidget - displays report history for a student.
"""
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QListWidget, QListWidgetItem,
    QSizePolicy, QMenu
)
from PySide6.QtGui import QAction

from centermanager.services.report_service import ReportService
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY

logger = logging.getLogger(__name__)


class ReportsWidget(QWidget):
    report_changed = Signal()

    def __init__(
        self,
        report_service: ReportService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = report_service
        self._student_id: Optional[int] = None
        self._reports: List[Dict[str, Any]] = []
        self._write_enabled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        # Header
        header = QHBoxLayout()
        title = QLabel("📄 Báo cáo học sinh")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.refresh_btn = QPushButton("🔄 Làm mới")
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # List
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
        self.list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_widget)

        self._show_empty()

    def _show_empty(self) -> None:
        self._clear_list()
        empty_item = QListWidgetItem("Chưa có báo cáo nào")
        empty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.list_widget.addItem(empty_item)

    def _clear_list(self) -> None:
        self.list_widget.clear()

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self.refresh()

    def refresh(self) -> None:
        if self._student_id is None:
            self._show_empty()
            return
        try:
            self._reports = self._service.get_reports_for_student(self._student_id)
            self._update_list()
        except Exception as e:
            logger.exception("Failed to load reports")
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách báo cáo: {str(e)}")

    def _update_list(self) -> None:
        self._clear_list()
        if not self._reports:
            self._show_empty()
            return

        for report in self._reports:
            item = QListWidgetItem()
            widget = self._create_report_item(report)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

    def _create_report_item(self, report: Dict[str, Any]) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        # Report type
        report_type = report.get("report_type", "Báo cáo")
        type_label = QLabel(report_type)
        type_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        info_layout.addWidget(type_label)

        # Generation info
        generated_by = report.get("generated_by", "System")
        gen_date = report.get("generation_date", "")
        if gen_date:
            try:
                dt = datetime.fromisoformat(gen_date)
                gen_date_str = dt.strftime("%d/%m/%Y %H:%M")
            except:
                gen_date_str = gen_date
        else:
            gen_date_str = ""

        sub_label = QLabel(f"Tạo bởi: {generated_by}  -  {gen_date_str}")
        sub_label.setStyleSheet("font-size: 11px; color: #666;")
        info_layout.addWidget(sub_label)

        # Auto/manual tag
        auto = report.get("auto_generated", False)
        tag = QLabel("Tự động" if auto else "Thủ công")
        tag.setStyleSheet(f"""
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 10px;
            background: {'#e8f5e9' if auto else '#e3f2fd'};
            color: {'#2e7d32' if auto else '#0d47a1'};
        """)
        tag.setFixedHeight(20)
        info_layout.addWidget(tag)

        layout.addLayout(info_layout)
        layout.addStretch()

        # Open button
        open_btn = QPushButton("📂 Mở")
        open_btn.setFixedHeight(28)
        open_btn.clicked.connect(lambda: self._open_report(report))
        layout.addWidget(open_btn)

        # Delete button
        delete_btn = QPushButton("🗑️")
        delete_btn.setFixedHeight(28)
        delete_btn.setStyleSheet("color: #d32f2f;")
        delete_btn.setEnabled(self._write_enabled)
        delete_btn.clicked.connect(lambda: self._delete_report(report))
        layout.addWidget(delete_btn)

        return widget

    def _open_report(self, report: Dict[str, Any]) -> None:
        pdf_path = report.get("pdf_path")
        if not pdf_path:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file PDF.")
            return
        path = Path(pdf_path)
        if not path.exists():
            QMessageBox.warning(self, "Lỗi", "File PDF không tồn tại.")
            return
        try:
            if sys.platform == 'win32':
                os.startfile(str(path))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(path)])
            else:
                subprocess.run(['xdg-open', str(path)])
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở file: {str(e)}")

    def _delete_report(self, report: Dict[str, Any]) -> None:
        meta_path = report.get("meta_path")
        if not meta_path:
            return
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa",
            "Bạn có chắc muốn xóa báo cáo này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_report(meta_path)
                self.refresh()
                self.report_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa báo cáo: {str(e)}")


    def set_write_enabled(self, enabled: bool) -> None:
        """Keep destructive report actions unavailable in read mode."""
        self._write_enabled = enabled
        self._update_list()

    def _on_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        widget = self.list_widget.itemWidget(item)
        if not widget:
            return
        # Find which report this widget corresponds to
        index = self.list_widget.row(item)
        if index >= len(self._reports):
            return
        report = self._reports[index]
        menu = QMenu(self)
        open_action = QAction("Mở", self)
        open_action.triggered.connect(lambda: self._open_report(report))
        menu.addAction(open_action)
        delete_action = QAction("Xóa", self)
        delete_action.setEnabled(self._write_enabled)
        delete_action.triggered.connect(lambda: self._delete_report(report))
        menu.addAction(delete_action)
        menu.exec(self.list_widget.mapToGlobal(pos))