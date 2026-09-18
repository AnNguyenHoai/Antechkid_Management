# -*- coding: utf-8 -*-
"""Expense list with filters, sorting, collaboration write guard, and CRUD."""
import logging
from typing import Optional
from PySide6.QtCore import Signal, QDate
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QMenu, QComboBox, QDateEdit

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
        self._write_enabled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        toolbar = QWidget(); toolbar.setStyleSheet(f"background: {COLORS['surface']}; padding: {SPACING['sm']}px {SPACING['md']}px; border-bottom: 1px solid {COLORS['border_light']};")
        toolbar_layout = QVBoxLayout(toolbar); toolbar_layout.setContentsMargins(0, 0, 0, 0)
        top_row = QHBoxLayout()
        self.search_bar = SearchBar("Tìm kiếm theo nội dung, người chi, ghi chú..."); self.search_bar.text_changed.connect(self._on_search); top_row.addWidget(self.search_bar)
        self.refresh_btn = SecondaryButton("🔄 Làm mới"); self.refresh_btn.clicked.connect(self.refresh); top_row.addWidget(self.refresh_btn)
        self.add_btn = PrimaryButton("+ Thêm chi phí"); self.add_btn.clicked.connect(self._show_add_dialog); top_row.addWidget(self.add_btn)
        toolbar_layout.addLayout(top_row)

        filters = QHBoxLayout()
        self.category_combo = QComboBox(); self.category_combo.addItems(["", "Teacher Salary", "Office Rent", "Electricity", "Water", "Internet", "Equipment", "Marketing", "Office Supply", "Maintenance", "Transportation", "Other"]); self.category_combo.currentTextChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Danh mục:")); filters.addWidget(self.category_combo)
        self.method_combo = QComboBox(); self.method_combo.addItems(["", "TÀI KHOẢN CÁ NHÂN", "TÀI KHOẢN CÔNG TY"]); self.method_combo.currentTextChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Hình thức chi:")); filters.addWidget(self.method_combo)
        self.status_combo = QComboBox(); self.status_combo.addItems(["", "ĐÃ HOÀN TRẢ", "CHƯA HOÀN TRẢ"]); self.status_combo.currentTextChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Trạng thái:")); filters.addWidget(self.status_combo)
        self.date_from = QDateEdit(); self.date_from.setCalendarPopup(True); self.date_from.setDisplayFormat("dd/MM/yyyy"); self.date_from.setDate(QDate.currentDate().addDays(-30)); self.date_from.dateChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Từ:")); filters.addWidget(self.date_from)
        self.date_to = QDateEdit(); self.date_to.setCalendarPopup(True); self.date_to.setDisplayFormat("dd/MM/yyyy"); self.date_to.setDate(QDate.currentDate()); self.date_to.dateChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Đến:")); filters.addWidget(self.date_to); filters.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc"); clear_btn.clicked.connect(self._clear_filters); filters.addWidget(clear_btn)
        toolbar_layout.addLayout(filters); layout.addWidget(toolbar)

        columns = [
            {"key": "payment_date", "label": "Ngày", "sortable": True}, {"key": "category", "label": "Danh mục", "sortable": True},
            {"key": "description", "label": "Nội dung", "sortable": False}, {"key": "amount", "label": "Số tiền", "sortable": True},
            {"key": "payment_method", "label": "Hình thức", "sortable": True}, {"key": "paid_by", "label": "Người chi", "sortable": False},
            {"key": "status", "label": "Trạng thái", "sortable": True},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table)
        self.loading = LoadingWidget(); self.loading.setVisible(False); layout.addWidget(self.loading)

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(self._notification_service, "notify"):
            self._notification_service.notify(message, level)
        else:
            logger.warning("Finance notification fallback: %s", message)

    def refresh(self) -> None:
        self.loading.setVisible(True)
        try: self._apply_filters()
        finally: self.loading.setVisible(False)

    def _apply_filters(self) -> None:
        items, _ = self._service.list_expenses(
            category=self.category_combo.currentText() or None,
            payment_method=self.method_combo.currentText() or None,
            status=self.status_combo.currentText() or None,
            date_from=self.date_from.date().toPython(), date_to=self.date_to.date().toPython(),
            search_text=self.search_bar.text().strip() or None, page=1, per_page=1000)
        self._expenses = items; self._populate_table()

    def _populate_table(self) -> None:
        data = [{"payment_date": exp.payment_date.strftime("%d/%m/%Y"), "category": exp.category,
                 "description": exp.description[:50] + ("..." if len(exp.description) > 50 else ""), "amount": f"{exp.amount:,.0f}",
                 "payment_method": exp.payment_method, "paid_by": exp.paid_by or "-", "status": exp.status} for exp in self._expenses]
        self.data_table.set_data(data, len(data))

    def _on_search(self, _text: str) -> None: self._apply_filters()

    def _on_sort(self, key: str, ascending: bool) -> None:
        getters = {"payment_date": lambda item: item.payment_date, "category": lambda item: item.category or "", "amount": lambda item: item.amount,
                   "payment_method": lambda item: item.payment_method or "", "status": lambda item: item.status or ""}
        getter = getters.get(key)
        if getter is None: return
        self._expenses.sort(key=getter, reverse=not ascending); self._populate_table()

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
        dialog = ExpenseFormDialog(self._service, parent=self)
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted: self.refresh()

    def _show_edit_dialog(self, expense_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to edit expense."); return
        dialog = ExpenseFormDialog(self._service, expense_id=expense_id, parent=self)
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted: self.refresh()

    def _show_detail_dialog(self, expense_id: int) -> None: ExpenseDetailDialog(self._service, expense_id, parent=self).exec()

    def _delete_expense(self, expense_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to delete expense."); return
        if QMessageBox.question(self, "Xác nhận xóa", "Bạn có chắc muốn xóa chi phí này?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._service.delete_expense(expense_id); self.refresh()

    def _clear_filters(self) -> None:
        self.search_bar.clear(); self.category_combo.setCurrentIndex(0); self.method_combo.setCurrentIndex(0); self.status_combo.setCurrentIndex(0)
        self.date_from.setDate(QDate.currentDate().addDays(-30)); self.date_to.setDate(QDate.currentDate()); self._apply_filters()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled); self.add_btn.setEnabled(self._write_enabled)
