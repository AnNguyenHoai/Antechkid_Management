# -*- coding: utf-8 -*-
"""Expense workspace with shared FinancePeriod, server paging/sort/filter and CSV export."""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Signal, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
    QMenu, QComboBox, QDateEdit, QFileDialog,
)

from centermanager.services.expense_service import ExpenseService
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.expense_detail_dialog import ExpenseDetailDialog
from centermanager.platform.collaboration import CollaborationManager

logger = logging.getLogger(__name__)


class ExpenseListPage(QWidget):
    expense_selected = Signal(int)

    def __init__(self, expense_service: ExpenseService, collaboration_manager: CollaborationManager,
                 notification_service=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = expense_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._expenses = []
        self._total_rows = 0
        self._current_page = 1
        self._page_size = 20
        self._sort_by = "payment_date"
        self._sort_ascending = False
        self._write_enabled = False
        self._target_date = date.today()
        self._period_start: Optional[date] = None
        self._period_end: Optional[date] = None
        self._period_configured = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background: {COLORS['surface']}; padding: {SPACING['sm']}px {SPACING['md']}px; "
            f"border-bottom: 1px solid {COLORS['border_light']};"
        )
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        top_row = QHBoxLayout()
        self.search_bar = SearchBar("Tìm kiếm theo nội dung, người chi, ghi chú...")
        self.search_bar.text_changed.connect(self._filters_changed)
        top_row.addWidget(self.search_bar)
        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)
        self.export_btn = SecondaryButton("⬇ Xuất CSV")
        self.export_btn.clicked.connect(self._export_csv)
        top_row.addWidget(self.export_btn)
        self.add_btn = PrimaryButton("+ Thêm chi phí")
        self.add_btn.clicked.connect(self._show_add_dialog)
        top_row.addWidget(self.add_btn)
        toolbar_layout.addLayout(top_row)

        filters = QHBoxLayout()
        self.category_combo = QComboBox()
        self.category_combo.addItem("Tất cả danh mục", "")
        for value in ["Teacher Salary", "Office Rent", "Electricity", "Water", "Internet", "Equipment", "Marketing", "Office Supply", "Maintenance", "Transportation", "Other"]:
            self.category_combo.addItem(value, value)
        self.category_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Danh mục:")); filters.addWidget(self.category_combo)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Tất cả hình thức", "")
        self.method_combo.addItem("TÀI KHOẢN CÁ NHÂN", "Cash")
        self.method_combo.addItem("TÀI KHOẢN CÔNG TY", "Bank")
        self.method_combo.addItem("Khác", "Other")
        self.method_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Hình thức chi:")); filters.addWidget(self.method_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Tất cả trạng thái", "")
        self.status_combo.addItem("ĐÃ HOÀN TRẢ", "Completed")
        self.status_combo.addItem("CHƯA HOÀN TRẢ", "Pending")
        self.status_combo.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Trạng thái:")); filters.addWidget(self.status_combo)

        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True); self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setDate(QDate.currentDate().addDays(-30)); self.date_from.dateChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Từ:")); filters.addWidget(self.date_from)
        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True); self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setDate(QDate.currentDate()); self.date_to.dateChanged.connect(self._filters_changed)
        filters.addWidget(QLabel("Đến:")); filters.addWidget(self.date_to)
        filters.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc"); clear_btn.clicked.connect(self._clear_filters); filters.addWidget(clear_btn)
        toolbar_layout.addLayout(filters)
        layout.addWidget(toolbar)

        columns = [
            {"key": "payment_date", "label": "Ngày", "sortable": True},
            {"key": "category", "label": "Danh mục", "sortable": True},
            {"key": "description", "label": "Nội dung", "sortable": True},
            {"key": "amount", "label": "Số tiền", "sortable": True},
            {"key": "payment_method", "label": "Hình thức", "sortable": True},
            {"key": "paid_by", "label": "Người chi", "sortable": True},
            {"key": "status", "label": "Trạng thái", "sortable": True},
        ]
        self.data_table = DataTable(columns, page_size=self._page_size)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.page_requested.connect(self._on_page_requested)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table)
        self.loading = LoadingWidget(); self.loading.setVisible(False); layout.addWidget(self.loading)

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(self._notification_service, "notify"):
            self._notification_service.notify(message, level)
        else:
            logger.warning("Finance notification fallback: %s", message)

    @staticmethod
    def _to_qdate(value: date) -> QDate:
        return QDate(value.year, value.month, value.day)

    def _reset_date_filters_to_period(self) -> None:
        if self._period_start is None or self._period_end is None:
            return
        for widget, value in ((self.date_from, self._period_start), (self.date_to, self._period_end)):
            previous = widget.blockSignals(True); widget.setDate(self._to_qdate(value)); widget.blockSignals(previous)

    def refresh(self, *_args, target_date=None, period_start=None, period_end=None,
                period_configured=None, **_kwargs) -> None:
        if target_date is not None:
            self._target_date = target_date
        period_changed = period_start is not None and period_end is not None and (
            period_start != self._period_start or period_end != self._period_end
        )
        if period_configured is not None:
            self._period_configured = period_configured
        if period_start is not None and period_end is not None:
            self._period_start, self._period_end = period_start, period_end
            if period_changed:
                self._reset_date_filters_to_period(); self._current_page = 1
        elif period_configured is False:
            self._period_start = None; self._period_end = None; self._current_page = 1
        self.loading.setVisible(True)
        try:
            self._load_page()
        except Exception as exc:
            logger.exception("Failed to refresh Expense Workspace")
            QMessageBox.critical(self, "Lỗi", str(exc))
        finally:
            self.loading.setVisible(False)

    def _default_transaction_date(self) -> date:
        """Choose a create date that belongs to the Finance period being viewed."""
        today = date.today()
        if self._period_start is None or self._period_end is None:
            return self._target_date or today
        if self._period_start <= today <= self._period_end:
            return today
        if self._period_start <= self._target_date <= self._period_end:
            return self._target_date
        return self._period_start

    def _effective_date_bounds(self):
        user_from, user_to = self.date_from.date().toPython(), self.date_to.date().toPython()
        if self._period_start is None or self._period_end is None:
            return user_from, user_to
        return max(user_from, self._period_start), min(user_to, self._period_end)

    def _filter_kwargs(self) -> dict:
        date_from, date_to = self._effective_date_bounds()
        return {
            "category": self.category_combo.currentData() or None,
            "payment_method": self.method_combo.currentData() or None,
            "status": self.status_combo.currentData() or None,
            "date_from": date_from,
            "date_to": date_to,
            "search_text": self.search_bar.text().strip() or None,
        }

    def _filters_changed(self, *_args) -> None:
        self._current_page = 1
        self._load_page()

    def _apply_filters(self) -> None:
        self._filters_changed()

    def _load_page(self) -> None:
        if self._period_configured is False:
            self._expenses = []; self._total_rows = 0; self._populate_table(); return
        kwargs = self._filter_kwargs()
        if kwargs["date_from"] > kwargs["date_to"]:
            self._expenses = []; self._total_rows = 0; self._populate_table(); return
        items, total = self._service.list_expenses(
            **kwargs,
            finance_period_start=self._period_start,
            page=self._current_page,
            per_page=self._page_size,
            sort_by=self._sort_by,
            ascending=self._sort_ascending,
        )
        max_page = max(1, (total + self._page_size - 1) // self._page_size)
        if self._current_page > max_page:
            self._current_page = max_page
            items, total = self._service.list_expenses(
                **kwargs, finance_period_start=self._period_start, page=self._current_page,
                per_page=self._page_size, sort_by=self._sort_by, ascending=self._sort_ascending,
            )
        self._expenses, self._total_rows = items, total
        self._populate_table()

    def _populate_table(self) -> None:
        data = [{
            "payment_date": exp.payment_date.strftime("%d/%m/%Y"), "category": exp.category,
            "description": (exp.description or "")[:50] + ("..." if len(exp.description or "") > 50 else ""),
            "amount": f"{exp.amount:,.0f}", "payment_method": exp.payment_method,
            "paid_by": exp.paid_by or "-", "status": exp.status,
        } for exp in self._expenses]
        self.data_table.set_server_data(data, self._total_rows, page=self._current_page, page_size=self._page_size)

    def _on_page_requested(self, page: int, page_size: int) -> None:
        self._current_page, self._page_size = page, page_size
        self._load_page()

    def _on_search(self, _text: str) -> None:
        self._filters_changed()

    def _on_sort(self, key: str, ascending: bool) -> None:
        if key not in {"payment_date", "category", "description", "amount", "payment_method", "paid_by", "status"}:
            return
        self._sort_by, self._sort_ascending, self._current_page = key, ascending, 1
        self._load_page()

    def _export_csv(self) -> None:
        if self._period_configured is False:
            self._notify("Finance period is not configured.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Xuất chi phí", "expenses.csv", "CSV Files (*.csv)")
        if not path:
            return
        try:
            count = self._service.export_expenses_csv(
                path, **self._filter_kwargs(), finance_period_start=self._period_start,
                sort_by=self._sort_by, ascending=self._sort_ascending,
            )
            self._notify(f"Đã xuất {count} khoản chi.", "success")
        except Exception as exc:
            logger.exception("Expense CSV export failed")
            QMessageBox.critical(self, "Lỗi xuất CSV", str(exc))

    def _on_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._expenses): self._show_detail_dialog(self._expenses[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._expenses): return
        exp = self._expenses[row]; menu = QMenu(self)
        menu.addAction("Xem", lambda: self._show_detail_dialog(exp.id))
        edit_action = menu.addAction("Sửa", lambda: self._show_edit_dialog(exp.id)); edit_action.setEnabled(self._write_enabled)
        delete_action = menu.addAction("Xóa", lambda: self._delete_expense(exp.id)); delete_action.setEnabled(self._write_enabled)
        menu.exec(pos)

    def _show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to add expense."); return
        dialog = ExpenseFormDialog(
            self._service,
            initial_payment_date=self._default_transaction_date(),
            parent=self,
        )
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted:
            self._current_page = 1
            self.refresh()

    def _show_edit_dialog(self, expense_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to edit expense."); return
        dialog = ExpenseFormDialog(self._service, expense_id=expense_id, parent=self)
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted: self.refresh()

    def _show_detail_dialog(self, expense_id: int) -> None:
        ExpenseDetailDialog(self._service, expense_id, parent=self).exec()

    def _delete_expense(self, expense_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to delete expense."); return
        if QMessageBox.question(self, "Xác nhận xóa", "Bạn có chắc muốn xóa chi phí này?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._service.delete_expense(expense_id); self.refresh()

    def _clear_filters(self) -> None:
        self.search_bar.clear()
        self.category_combo.setCurrentIndex(0); self.method_combo.setCurrentIndex(0); self.status_combo.setCurrentIndex(0)
        if self._period_start is not None and self._period_end is not None:
            self._reset_date_filters_to_period()
        else:
            self.date_from.setDate(QDate.currentDate().addDays(-30)); self.date_to.setDate(QDate.currentDate())
        self._current_page = 1; self._load_page()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled); self.add_btn.setEnabled(self._write_enabled)
