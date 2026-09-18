# -*- coding: utf-8 -*-
"""Income list with filters, sorting, collaboration write guard, and CRUD."""
import logging
from typing import Optional
from datetime import date

from PySide6.QtCore import Signal, QDate
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QMenu, QComboBox, QDateEdit

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog
from centermanager.ui.finance_workspace.income_detail_dialog import IncomeDetailDialog
from centermanager.platform.collaboration import CollaborationManager

logger = logging.getLogger(__name__)


class IncomeListPage(QWidget):
    income_selected = Signal(int)

    def __init__(self, income_service: IncomeService, student_service: StudentService,
                 class_service: ClassService, collaboration_manager: CollaborationManager,
                 notification_service=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._incomes = []
        self._write_enabled = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolbar = QWidget()
        toolbar.setStyleSheet(f"background: {COLORS['surface']}; padding: {SPACING['sm']}px {SPACING['md']}px; border-bottom: 1px solid {COLORS['border_light']};")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        top_row = QHBoxLayout()
        self.search_bar = SearchBar("Tìm kiếm theo học sinh, lớp, ghi chú, kỳ...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)
        self.refresh_btn = SecondaryButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)
        self.add_btn = PrimaryButton("+ Thêm thu nhập")
        self.add_btn.clicked.connect(self._show_add_dialog)
        top_row.addWidget(self.add_btn)
        toolbar_layout.addLayout(top_row)

        filters = QHBoxLayout()
        self.type_combo = QComboBox(); self.type_combo.addItem("Tất cả loại", "")
        for value in ["Tuition", "Book", "Robot Kit", "Material", "Other"]: self.type_combo.addItem(value, value)
        self.type_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Loại:")); filters.addWidget(self.type_combo)
        self.method_combo = QComboBox(); self.method_combo.addItem("Tất cả hình thức", "")
        for value in ["Cash", "Bank Transfer"]: self.method_combo.addItem(value, value)
        self.method_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Hình thức:")); filters.addWidget(self.method_combo)
        self.period_combo = QComboBox(); self.period_combo.addItem("Tất cả kỳ", "")
        current_year = date.today().year
        for year in range(current_year - 1, current_year + 1):
            for month in range(1, 13):
                period = f"Tháng {month}/{year}"; self.period_combo.addItem(period, period)
        self.period_combo.currentIndexChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Kỳ:")); filters.addWidget(self.period_combo)
        self.date_from_edit = QDateEdit(); self.date_from_edit.setCalendarPopup(True); self.date_from_edit.setDisplayFormat("dd/MM/yyyy"); self.date_from_edit.setDate(QDate.currentDate().addDays(-30)); self.date_from_edit.dateChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Từ:")); filters.addWidget(self.date_from_edit)
        self.date_to_edit = QDateEdit(); self.date_to_edit.setCalendarPopup(True); self.date_to_edit.setDisplayFormat("dd/MM/yyyy"); self.date_to_edit.setDate(QDate.currentDate()); self.date_to_edit.dateChanged.connect(self._apply_filters)
        filters.addWidget(QLabel("Đến:")); filters.addWidget(self.date_to_edit)
        filters.addStretch()
        clear_btn = QPushButton("Xóa bộ lọc"); clear_btn.clicked.connect(self._clear_filters); filters.addWidget(clear_btn)
        toolbar_layout.addLayout(filters)
        layout.addWidget(toolbar)

        columns = [
            {"key": "payment_date", "label": "Ngày", "sortable": True}, {"key": "source", "label": "Nguồn thu", "sortable": False},
            {"key": "student_name", "label": "Học sinh", "sortable": False}, {"key": "class_name", "label": "Lớp", "sortable": False},
            {"key": "income_type", "label": "Loại", "sortable": True}, {"key": "amount", "label": "Số tiền", "sortable": True},
            {"key": "payment_method", "label": "Hình thức", "sortable": True}, {"key": "payment_period", "label": "Kỳ", "sortable": True},
            {"key": "received_by", "label": "Người thu", "sortable": False}, {"key": "note", "label": "Ghi chú", "sortable": False},
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
        items, _ = self._income_service.list_incomes(
            income_type=self.type_combo.currentData() or None,
            payment_method=self.method_combo.currentData() or None,
            payment_period=self.period_combo.currentData() or None,
            date_from=self.date_from_edit.date().toPython(), date_to=self.date_to_edit.date().toPython(),
            search_text=self.search_bar.text().strip() or None, page=1, per_page=1000)
        self._incomes = items
        self._populate_table()

    def _populate_table(self) -> None:
        data = []
        for income in self._incomes:
            linked = income.student_id is not None
            data.append({"payment_date": income.payment_date.strftime("%d/%m/%Y"), "source": "Học sinh" if linked else "Khác",
                         "student_name": income.student.full_name if linked and income.student else "-", "class_name": income.class_.name if linked and income.class_ else "-",
                         "income_type": income.income_type, "amount": f"{income.amount:,.0f}", "payment_method": income.payment_method,
                         "payment_period": income.payment_period or "-", "received_by": income.received_by or "-", "note": income.note or "-"})
        self.data_table.set_data(data, len(data))

    def _on_search(self, _text: str) -> None: self._apply_filters()

    def _on_sort(self, key: str, ascending: bool) -> None:
        getters = {"payment_date": lambda item: item.payment_date, "income_type": lambda item: item.income_type or "",
                   "amount": lambda item: item.amount, "payment_method": lambda item: item.payment_method or "",
                   "payment_period": lambda item: item.payment_period or ""}
        getter = getters.get(key)
        if getter is None: return
        self._incomes.sort(key=getter, reverse=not ascending)
        self._populate_table()

    def _on_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._incomes): self._show_detail_dialog(self._incomes[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._incomes): return
        income = self._incomes[row]; menu = QMenu(self)
        menu.addAction("Xem", lambda: self._show_detail_dialog(income.id))
        edit_action = menu.addAction("Sửa", lambda: self._show_edit_dialog(income.id)); edit_action.setEnabled(self._write_enabled)
        delete_action = menu.addAction("Xóa", lambda: self._delete_income(income.id)); delete_action.setEnabled(self._write_enabled)
        menu.exec(pos)

    def _show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to add income."); return
        dialog = IncomeFormDialog(self._income_service, self._student_service, self._class_service, parent=self)
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted: self.refresh()

    def _show_edit_dialog(self, income_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to edit income."); return
        dialog = IncomeFormDialog(self._income_service, self._student_service, self._class_service, income_id=income_id, parent=self)
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted: self.refresh()

    def _show_detail_dialog(self, income_id: int) -> None: IncomeDetailDialog(self._income_service, income_id, parent=self).exec()

    def _delete_income(self, income_id: int) -> None:
        if not self._collaboration_manager.ensure_write(): self._notify("You must be in WRITE mode to delete income."); return
        if QMessageBox.question(self, "Xác nhận xóa", "Bạn có chắc muốn xóa khoản thu này?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._income_service.delete_income(income_id); self.refresh()

    def _clear_filters(self) -> None:
        self.search_bar.clear(); self.type_combo.setCurrentIndex(0); self.method_combo.setCurrentIndex(0); self.period_combo.setCurrentIndex(0)
        self.date_from_edit.setDate(QDate.currentDate().addDays(-30)); self.date_to_edit.setDate(QDate.currentDate()); self._apply_filters()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.add_btn.setEnabled(self._write_enabled)
