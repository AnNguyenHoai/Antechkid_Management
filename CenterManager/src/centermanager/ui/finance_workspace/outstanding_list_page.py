# -*- coding: utf-8 -*-
"""
OutstandingListPage - Display outstanding tuition for all students.
Read-only. No write actions needed.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QComboBox, QLineEdit, QSizePolicy
)

from centermanager.services.outstanding_service import OutstandingService
from centermanager.dto.outstanding_dto import OutstandingDTO
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget, EmptyState
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class OutstandingListPage(QWidget):
    STATUS_NO_TUITION_CONFIGURED = "No Tuition Configured"
    student_selected = Signal(int)

    def __init__(
        self,
        outstanding_service: OutstandingService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = outstanding_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._items: List[OutstandingDTO] = []
        self._setup_ui()
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            background: {COLORS['surface']};
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border-bottom: 1px solid {COLORS['border_light']};
        """)
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['xs'])

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACING['sm'])

        self.search_bar = SearchBar("Tìm kiếm theo tên học sinh, mã...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        top_row.addStretch()
        toolbar_layout.addLayout(top_row)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACING['sm'])

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Tất cả trạng thái", "Paid", "Partial", "Overpaid"])
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Trạng thái:"))
        filter_row.addWidget(self.status_combo)

        filter_row.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc")
        clear_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(clear_btn)

        toolbar_layout.addLayout(filter_row)
        layout.addWidget(toolbar)

        # Data Table
        columns = [
            {"key": "student_code", "label": "Mã HS", "sortable": True},
            {"key": "student_name", "label": "Học sinh", "sortable": True},
            {"key": "class_name", "label": "Lớp", "sortable": True},
            {"key": "expected_tuition", "label": "Học phí dự kiến", "sortable": True},
            {"key": "paid", "label": "Đã đóng", "sortable": True},
            {"key": "outstanding", "label": "Còn nợ", "sortable": True},
            {"key": "status", "label": "Trạng thái", "sortable": True},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.data_table)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def refresh(self) -> None:
        self.loading.setVisible(True)
        try:
            self._apply_filters()
        except Exception as e:
            logger.exception("Refresh failed")
            QMessageBox.critical(self, "Lỗi", "Không thể tải dữ liệu công nợ.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters(self) -> None:
        search = self.search_bar.text().strip() or None
        status = self.status_combo.currentText()
        if status == "Tất cả trạng thái":
            status = None

        try:
            items, total = self._service.get_all_outstanding(
                search_text=search,
                status_filter=status,
                offset=0,
                limit=1000
            )
            self._items = items
            self._populate_table()
            logger.info(f"Loaded {len(items)} outstanding items")
        except Exception as e:
            logger.exception("Filter error")
            QMessageBox.critical(self, "Lỗi", str(e))

    def _populate_table(self) -> None:
        data = []
        for item in self._items:
            data.append({
                "student_code": item.student_code,
                "student_name": item.student_name,
                "class_name": item.class_name,
                "expected_tuition": f"{item.expected_tuition:,.0f}",
                "paid": f"{item.paid:,.0f}",
                "outstanding": f"{item.outstanding:,.0f}",
                "status": item.status,
                "_id": item.student_id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text) -> None:
        self._apply_filters()

    def _on_sort(self, key: str, ascending: bool) -> None:
        if key == "student_code":
            self._items.sort(key=lambda x: x.student_code, reverse=not ascending)
        elif key == "student_name":
            self._items.sort(key=lambda x: x.student_name, reverse=not ascending)
        elif key == "class_name":
            self._items.sort(key=lambda x: x.class_name, reverse=not ascending)
        elif key == "expected_tuition":
            self._items.sort(key=lambda x: x.expected_tuition, reverse=not ascending)
        elif key == "paid":
            self._items.sort(key=lambda x: x.paid, reverse=not ascending)
        elif key == "outstanding":
            self._items.sort(key=lambda x: x.outstanding, reverse=not ascending)
        elif key == "status":
            self._items.sort(key=lambda x: x.status, reverse=not ascending)
        self._populate_table()

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._items):
            student_id = self._items[row].student_id
            self.student_selected.emit(student_id)

    def _clear_filters(self) -> None:
        self.search_bar.clear()
        self.status_combo.setCurrentIndex(0)
        self._apply_filters()

    def set_write_enabled(self, enabled: bool) -> None:
        # Outstanding is read-only, no actions to enable/disable
        pass
# "Chưa xác định"
# "Chưa cấu hình"