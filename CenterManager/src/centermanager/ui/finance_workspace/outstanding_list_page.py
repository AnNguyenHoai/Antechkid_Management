# -*- coding: utf-8 -*-
"""Outstanding Workspace - read-only, period-aware tuition debt management."""
import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.dto.outstanding_dto import OutstandingDTO
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.ui.design_system import SearchBar, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget

logger = logging.getLogger(__name__)


class OutstandingListPage(QWidget):
    # Keep the canonical status value explicit at the UI filter boundary. This
    # value is persisted nowhere; it is passed back to OutstandingService only.
    STATUS_NO_TUITION_CONFIGURED = "No Tuition Configured"
    student_selected = Signal(int)

    def __init__(
        self,
        outstanding_service: OutstandingService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = outstanding_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._items: List[OutstandingDTO] = []
        self._target_date = date.today()
        self._period_start: Optional[date] = None
        self._period_configured = None
        self._current_page = 1
        self._page_size = 20
        self._total_rows = 0
        self._sort_by = "outstanding"
        self._sort_ascending = False
        self._setup_ui()
        # Protected Finance data is loaded only after FinanceWorkspaceShell
        # resolves authorization and the shared Finance Period.

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background: {COLORS['surface']}; "
            f"padding: {SPACING['sm']}px {SPACING['md']}px; "
            f"border-bottom: 1px solid {COLORS['border_light']};"
        )
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING["xs"])

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACING["sm"])
        self.search_bar = SearchBar(
            "Tìm theo tên học sinh, mã, lớp hoặc khóa học..."
        )
        self.search_bar.text_changed.connect(self._filters_changed)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.export_btn = SecondaryButton("⬇ Xuất CSV")
        self.export_btn.setFixedHeight(34)
        self.export_btn.clicked.connect(self._export_csv)
        top_row.addWidget(self.export_btn)
        top_row.addStretch()
        toolbar_layout.addLayout(top_row)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACING["sm"])

        self.status_combo = QComboBox()
        self.status_combo.addItem("Tất cả trạng thái", None)
        self.status_combo.addItem("Chưa đóng", "Not Yet")
        self.status_combo.addItem("Đóng một phần", "Partial")
        self.status_combo.addItem("Đã đóng đủ", "Paid")
        self.status_combo.addItem("Đóng dư", "Overpaid")
        self.status_combo.addItem(
            "Chưa cấu hình học phí", self.STATUS_NO_TUITION_CONFIGURED
        )
        self.status_combo.currentIndexChanged.connect(self._filters_changed)
        filter_row.addWidget(QLabel("Trạng thái:"))
        filter_row.addWidget(self.status_combo)

        self.class_combo = QComboBox()
        self.class_combo.addItem("Tất cả lớp", None)
        self.class_combo.currentIndexChanged.connect(self._filters_changed)
        filter_row.addWidget(QLabel("Lớp:"))
        filter_row.addWidget(self.class_combo)

        filter_row.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc")
        clear_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(clear_btn)
        toolbar_layout.addLayout(filter_row)
        layout.addWidget(toolbar)

        kpi_row = QHBoxLayout()
        kpi_row.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        kpi_row.setSpacing(SPACING["lg"])
        self.expected_kpi = QLabel("Phải thu: 0 VND")
        self.paid_kpi = QLabel("Đã thu: 0 VND")
        self.outstanding_kpi = QLabel("Còn nợ: 0 VND")
        self.debt_students_kpi = QLabel("HS còn nợ: 0")
        self.unconfigured_kpi = QLabel("Chưa cấu hình HP: 0")
        for widget in (
            self.expected_kpi,
            self.paid_kpi,
            self.outstanding_kpi,
            self.debt_students_kpi,
            self.unconfigured_kpi,
        ):
            kpi_row.addWidget(widget)
        kpi_row.addStretch()
        layout.addLayout(kpi_row)

        columns = [
            {"key": "student_code", "label": "Mã HS", "sortable": True},
            {"key": "student_name", "label": "Học sinh", "sortable": True},
            {"key": "class_name", "label": "Lớp", "sortable": True},
            {
                "key": "expected_tuition",
                "label": "Học phí dự kiến",
                "sortable": True,
            },
            {"key": "paid", "label": "Đã đóng", "sortable": True},
            {"key": "outstanding", "label": "Còn nợ", "sortable": True},
            {"key": "status", "label": "Trạng thái", "sortable": True},
        ]
        self.data_table = DataTable(columns, page_size=self._page_size)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.page_requested.connect(self._on_page_requested)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.data_table)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def _notify(self, message: str, level: str = "info") -> None:
        if self._notification_service is not None and hasattr(
            self._notification_service, "notify"
        ):
            self._notification_service.notify(message, level)
        else:
            logger.info("Outstanding notification: %s", message)

    def refresh(
        self,
        *_args,
        target_date: Optional[date] = None,
        period_start=None,
        period_end=None,
        period_configured=None,
        **_kwargs,
    ) -> None:
        del period_end
        previous_period = self._period_start
        if target_date is not None:
            self._target_date = target_date
        if period_configured is not None:
            self._period_configured = period_configured
        if period_start is not None:
            self._period_start = period_start
        elif period_configured is False:
            self._period_start = None

        if previous_period != self._period_start:
            self._current_page = 1

        self.loading.setVisible(True)
        try:
            if self._period_configured is False:
                self._items = []
                self._total_rows = 0
                self._populate_table()
                self._update_kpis({})
                self._load_class_filter([])
                return
            self._load_class_filter(
                self._service.list_outstanding_classes(
                    period_start=self._period_start,
                    on_date=self._target_date,
                )
            )
            self._load_page()
        except Exception:
            logger.exception("Outstanding refresh failed")
            QMessageBox.critical(self, "Lỗi", "Không thể tải dữ liệu công nợ.")
        finally:
            self.loading.setVisible(False)

    def _load_class_filter(self, classes) -> None:
        selected = self.class_combo.currentData()
        previous = self.class_combo.blockSignals(True)
        self.class_combo.clear()
        self.class_combo.addItem("Tất cả lớp", None)
        for class_id, class_name in classes:
            self.class_combo.addItem(class_name, class_id)
        selected_index = self.class_combo.findData(selected)
        self.class_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
        self.class_combo.blockSignals(previous)

    def _filter_kwargs(self) -> dict:
        return {
            "class_id": self.class_combo.currentData(),
            "status_filter": self.status_combo.currentData(),
            "search_text": self.search_bar.text().strip() or None,
        }

    def _filters_changed(self, *_args) -> None:
        self._current_page = 1
        self._load_page()

    def _load_page(self) -> None:
        if self._period_configured is False:
            self._items = []
            self._total_rows = 0
            self._populate_table()
            self._update_kpis({})
            return

        items, total, stats = self._service.get_outstanding_page(
            **self._filter_kwargs(),
            offset=(self._current_page - 1) * self._page_size,
            limit=self._page_size,
            period_start=self._period_start,
            on_date=self._target_date,
            sort_by=self._sort_by,
            ascending=self._sort_ascending,
        )
        max_page = max(1, (total + self._page_size - 1) // self._page_size)
        if self._current_page > max_page:
            self._current_page = max_page
            items, total, stats = self._service.get_outstanding_page(
                **self._filter_kwargs(),
                offset=(self._current_page - 1) * self._page_size,
                limit=self._page_size,
                period_start=self._period_start,
                on_date=self._target_date,
                sort_by=self._sort_by,
                ascending=self._sort_ascending,
            )

        self._items = items
        self._total_rows = total
        self._populate_table()
        self._update_kpis(stats)
        logger.info(
            "Loaded outstanding page %s (%s/%s rows)",
            self._current_page,
            len(items),
            total,
        )

    def _populate_table(self) -> None:
        data = []
        for item in self._items:
            if item.tuition_configured:
                expected_tuition = f"{item.expected_tuition:,.0f}"
                outstanding = f"{item.outstanding:,.0f}"
                status = item.status
            else:
                expected_tuition = "Chưa cấu hình"
                outstanding = "Chưa xác định"
                status = "Chưa cấu hình"

            data.append(
                {
                    "student_code": item.student_code,
                    "student_name": item.student_name,
                    "class_name": item.class_name,
                    "expected_tuition": expected_tuition,
                    "paid": f"{item.paid:,.0f}",
                    "outstanding": outstanding,
                    "status": status,
                    "_id": item.student_id,
                }
            )
        self.data_table.set_server_data(
            data,
            self._total_rows,
            page=self._current_page,
            page_size=self._page_size,
        )

    def _update_kpis(self, stats: dict) -> None:
        total_expected = int(stats.get("total_expected", 0))
        total_paid = int(stats.get("total_paid", 0))
        total_outstanding = int(stats.get("total_outstanding", 0))
        total_debt_students = int(stats.get("total_students_with_debt", 0))
        total_unconfigured = int(stats.get("total_unconfigured_tuition", 0))
        self.expected_kpi.setText(f"Phải thu: {total_expected:,.0f} VND")
        self.paid_kpi.setText(f"Đã thu: {total_paid:,.0f} VND")
        self.outstanding_kpi.setText(f"Còn nợ: {total_outstanding:,.0f} VND")
        self.debt_students_kpi.setText(f"HS còn nợ: {total_debt_students}")
        self.unconfigured_kpi.setText(f"Chưa cấu hình HP: {total_unconfigured}")

    def _on_page_requested(self, page: int, page_size: int) -> None:
        self._current_page = page
        self._page_size = page_size
        self._load_page()

    def _on_sort(self, key: str, ascending: bool) -> None:
        allowed = {
            "student_code",
            "student_name",
            "class_name",
            "expected_tuition",
            "paid",
            "outstanding",
            "status",
        }
        if key not in allowed:
            return
        self._sort_by = key
        self._sort_ascending = ascending
        self._current_page = 1
        self._load_page()

    def _on_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self.student_selected.emit(self._items[row].student_id)

    def _clear_filters(self) -> None:
        status_blocked = self.status_combo.blockSignals(True)
        class_blocked = self.class_combo.blockSignals(True)
        self.search_bar.clear()
        self.status_combo.setCurrentIndex(0)
        self.class_combo.setCurrentIndex(0)
        self.status_combo.blockSignals(status_blocked)
        self.class_combo.blockSignals(class_blocked)
        self._current_page = 1
        self._load_page()

    def _export_csv(self) -> None:
        if self._period_configured is False:
            self._notify("Finance period is not configured.", "warning")
            return
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất Outstanding CSV",
            "outstanding_export.csv",
            "CSV files (*.csv)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".csv"):
            filename += ".csv"
        try:
            csv_text = self._service.export_outstanding_csv(
                **self._filter_kwargs(),
                period_start=self._period_start,
                on_date=self._target_date,
                sort_by=self._sort_by,
                ascending=self._sort_ascending,
            )
            Path(filename).write_text(csv_text, encoding="utf-8-sig")
            self._notify("Xuất công nợ CSV thành công.")
        except Exception as exc:
            logger.exception("Outstanding CSV export failed")
            QMessageBox.critical(self, "Lỗi xuất CSV", str(exc))

    def set_write_enabled(self, enabled: bool) -> None:
        del enabled
        # Outstanding is a read-only derived read model. Money mutations remain
        # exclusively in Finance Income/Expense workspaces.
