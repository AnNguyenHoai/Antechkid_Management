# -*- coding: utf-8 -*-
"""
ExpenseListPage - list of expenses with search, filter, CRUD.
Now with collaboration support.
"""
import logging
from typing import Optional, List
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QComboBox, QDateEdit, QSizePolicy
)

from centermanager.services.expense_service import ExpenseService
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.finance_workspace.expense_form_dialog import ExpenseFormDialog
from centermanager.ui.finance_workspace.expense_detail_dialog import ExpenseDetailDialog
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class ExpenseListPage(QWidget):
    expense_selected = Signal(int)

    def __init__(
        self,
        expense_service: ExpenseService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = expense_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._expenses = []
        self._selected_ids = []

        self._setup_ui()
        self.refresh()

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

        self.search_bar = SearchBar("Tìm kiếm theo nội dung, người chi, ghi chú...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Thêm chi phí")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self._show_add_dialog)
        top_row.addWidget(self.add_btn)

        toolbar_layout.addLayout(top_row)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACING['sm'])

        self.category_combo = QComboBox()
        categories = ["", "Teacher Salary", "Office Rent", "Electricity", "Water",
                      "Internet", "Equipment", "Marketing", "Office Supply",
                      "Maintenance", "Transportation", "Other"]
        self.category_combo.addItems(categories)
        self.category_combo.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Danh mục:"))
        filter_row.addWidget(self.category_combo)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["", "TÀI KHOẢN CÁ NHÂN", "TÀI KHOẢN CÔNG TY"])
        self.method_combo.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Hình thức chi:"))
        filter_row.addWidget(self.method_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["", "ĐÃ HOÀN TRẢ", "CHƯA HOÀN TRẢ"])
        self.status_combo.currentTextChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Trạng thái:"))
        filter_row.addWidget(self.status_combo)

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("dd/MM/yyyy")
        self.date_from.setSpecialValueText("Từ ngày")
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.dateChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Từ:"))
        filter_row.addWidget(self.date_from)

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("dd/MM/yyyy")
        self.date_to.setSpecialValueText("Đến ngày")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._apply_filters)
        filter_row.addWidget(QLabel("Đến:"))
        filter_row.addWidget(self.date_to)

        filter_row.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc")
        clear_btn.clicked.connect(self._clear_filters)
        filter_row.addWidget(clear_btn)

        toolbar_layout.addLayout(filter_row)
        layout.addWidget(toolbar)

        # Data Table
        columns = [
            {"key": "payment_date", "label": "Ngày", "sortable": True},
            {"key": "category", "label": "Danh mục", "sortable": True},
            {"key": "description", "label": "Nội dung", "sortable": False},
            {"key": "amount", "label": "Số tiền", "sortable": True},
            {"key": "payment_method", "label": "Hình thức", "sortable": True},
            {"key": "paid_by", "label": "Người chi", "sortable": False},
            {"key": "status", "label": "Trạng thái", "sortable": True},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
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
            QMessageBox.critical(self, "Lỗi", "Không thể tải danh sách chi phí")
        finally:
            self.loading.setVisible(False)

    def _apply_filters(self) -> None:
        search = self.search_bar.text().strip() or None
        category = self.category_combo.currentText() or None
        method = self.method_combo.currentText() or None
        status = self.status_combo.currentText() or None
        date_from = self.date_from.date().toPython() if self.date_from.date().isValid() else None
        date_to = self.date_to.date().toPython() if self.date_to.date().isValid() else None

        try:
            items, total = self._service.list_expenses(
                category=category,
                payment_method=method,
                status=status,
                date_from=date_from,
                date_to=date_to,
                search_text=search,
                page=1,
                per_page=1000
            )
            self._expenses = items
            self._populate_table()
        except Exception as e:
            logger.exception("Filter error")
            QMessageBox.critical(self, "Lỗi", str(e))

    def _populate_table(self) -> None:
        data = []
        for exp in self._expenses:
            data.append({
                "payment_date": exp.payment_date.strftime("%d/%m/%Y"),
                "category": exp.category,
                "description": exp.description[:50] + ("..." if len(exp.description) > 50 else ""),
                "amount": f"{exp.amount:,.0f}",
                "payment_method": exp.payment_method,
                "paid_by": exp.paid_by or "-",
                "status": exp.status,
                "_id": exp.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text) -> None:
        self._apply_filters()

    def _on_row_double_clicked(self, row) -> None:
        if row < len(self._expenses):
            self._show_detail_dialog(self._expenses[row].id)

    def _on_context_menu(self, pos, row) -> None:
        if row < 0 or row >= len(self._expenses):
            return
        exp = self._expenses[row]
        menu = QMenu(self)
        view_action = menu.addAction("Xem")
        view_action.triggered.connect(lambda: self._show_detail_dialog(exp.id))
        edit_action = menu.addAction("Sửa")
        edit_action.triggered.connect(lambda: self._show_edit_dialog(exp.id))
        delete_action = menu.addAction("Xóa")
        delete_action.triggered.connect(lambda: self._delete_expense(exp.id))
        menu.exec(pos)

    def _show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to add expense.", "warning")
            return
        dialog = ExpenseFormDialog(self._service, parent=self)
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_edit_dialog(self, expense_id) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to edit expense.", "warning")
            return
        dialog = ExpenseFormDialog(self._service, expense_id=expense_id, parent=self)
        if dialog.exec() == ExpenseFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_detail_dialog(self, expense_id) -> None:
        dialog = ExpenseDetailDialog(self._service, expense_id, parent=self)
        dialog.exec()

    def _delete_expense(self, expense_id) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to delete expense.", "warning")
            return
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            "Bạn có chắc muốn xóa chi phí này?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self._service.delete_expense(expense_id)
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", str(e))

    def _clear_filters(self) -> None:
        self.search_bar.clear()
        self.category_combo.setCurrentIndex(0)
        self.method_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_to.setDate(QDate.currentDate())
        self._apply_filters()

    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled)
# edit_action.setEnabled(self._write_enabled)
# delete_action.setEnabled(self._write_enabled)