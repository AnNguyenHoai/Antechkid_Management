# -*- coding: utf-8 -*-
"""
IncomeListPage - lists income records with search, filter, CRUD.
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import date, datetime

from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QSizePolicy, QComboBox, QLineEdit,
    QDateEdit, QFormLayout, QDialog, QDialogButtonBox
)

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.ui.design_system import (
    SearchBar, EmptyState, PrimaryButton, SecondaryButton,
    FilterBar, SectionHeader
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog
from centermanager.ui.finance_workspace.income_detail_dialog import IncomeDetailDialog

logger = logging.getLogger(__name__)


class IncomeListPage(QWidget):
    income_selected = Signal(int)

    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._incomes = []
        self._filtered = []
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

        self.search_bar = SearchBar("Search by student, class, note, period...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Add Income")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self._show_add_dialog)
        top_row.addWidget(self.add_btn)

        toolbar_layout.addLayout(top_row)

        # Filter bar (collapsible?)
        self.filter_widget = QWidget()
        filter_layout = QHBoxLayout(self.filter_widget)
        filter_layout.setContentsMargins(0, SPACING['xs'], 0, SPACING['xs'])
        filter_layout.setSpacing(SPACING['sm'])

        self.type_combo = QComboBox()
        self.type_combo.addItem("All Types", "")
        for t in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(t, t)
        self.type_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(QLabel("Type:"))
        filter_layout.addWidget(self.type_combo)

        self.method_combo = QComboBox()
        self.method_combo.addItem("All Methods", "")
        for m in ["Cash", "Bank Transfer"]:
            self.method_combo.addItem(m, m)
        self.method_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(QLabel("Method:"))
        filter_layout.addWidget(self.method_combo)

        # Filter by period
        self.period_combo = QComboBox()
        self.period_combo.addItem("All Periods", "")
        # Add some common periods
        current_year = date.today().year
        for year in range(current_year - 1, current_year + 1):
            for month in range(1, 13):
                period = f"Tháng {month}/{year}"
                self.period_combo.addItem(period, period)
        self.period_combo.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(QLabel("Period:"))
        filter_layout.addWidget(self.period_combo)

        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_from_edit.setSpecialValueText("From")
        self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
        self.date_from_edit.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_from_edit)

        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_to_edit.setSpecialValueText("To")
        self.date_to_edit.setDate(QDate.currentDate())
        self.date_to_edit.dateChanged.connect(self._apply_filters)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_to_edit)

        filter_layout.addStretch()
        clear_filter_btn = QPushButton("Clear Filters")
        clear_filter_btn.clicked.connect(self._clear_filters)
        filter_layout.addWidget(clear_filter_btn)

        toolbar_layout.addWidget(self.filter_widget)

        layout.addWidget(toolbar)

        # Data Table
        columns = [
            {"key": "payment_date", "label": "Date", "sortable": True},
            {"key": "student_name", "label": "Student", "sortable": False},
            {"key": "class_name", "label": "Class", "sortable": False},
            {"key": "income_type", "label": "Type", "sortable": True},
            {"key": "amount", "label": "Amount", "sortable": True},
            {"key": "payment_method", "label": "Method", "sortable": True},
            {"key": "payment_period", "label": "Period", "sortable": True},
            {"key": "received_by", "label": "Received By", "sortable": False},
            {"key": "note", "label": "Note", "sortable": False},
            {"key": "actions", "label": "Actions", "sortable": False},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.sort_requested.connect(self._on_sort)
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
            logger.exception("Failed to refresh income list")
            QMessageBox.critical(self, "Error", "Failed to load incomes.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters(self) -> None:
        search_text = self.search_bar.text().strip() or None
        income_type = self.type_combo.currentData() or None
        payment_method = self.method_combo.currentData() or None
        payment_period = self.period_combo.currentData() or None
        date_from = self.date_from_edit.date().toPython() if self.date_from_edit.date().isValid() else None
        date_to = self.date_to_edit.date().toPython() if self.date_to_edit.date().isValid() else None

        try:
            items, total = self._income_service.list_incomes(
                income_type=income_type,
                payment_method=payment_method,
                payment_period=payment_period,
                date_from=date_from,
                date_to=date_to,
                search_text=search_text,
                page=1,
                per_page=1000  # DataTable handles pagination internally
            )
            self._incomes = items
            self._populate_table()
        except Exception as e:
            logger.exception("Filter failed")
            QMessageBox.critical(self, "Filter Error", str(e))

    def _populate_table(self) -> None:
        data = []
        for income in self._incomes:
            data.append({
                "payment_date": income.payment_date.strftime("%d/%m/%Y"),
                "student_name": income.student.full_name if income.student else "-",
                "class_name": income.class_.name if income.class_ else "-",
                "income_type": income.income_type,
                "amount": f"{income.amount:,.0f}",
                "payment_method": income.payment_method,
                "payment_period": income.payment_period or "-",
                "received_by": income.received_by or "-",
                "note": income.note or "-",
                "_id": income.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
        self._apply_filters()

    def _on_sort(self, key: str, ascending: bool) -> None:
        # Implement sorting if needed
        pass

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._incomes):
            self._show_detail_dialog(self._incomes[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._incomes):
            return
        income = self._incomes[row]
        menu = QMenu(self)
        view_action = menu.addAction("View Income")
        view_action.triggered.connect(lambda: self._show_detail_dialog(income.id))
        edit_action = menu.addAction("Edit Income")
        edit_action.triggered.connect(lambda: self._show_edit_dialog(income.id))
        delete_action = menu.addAction("Delete Income")
        delete_action.triggered.connect(lambda: self._delete_income(income.id))
        menu.exec(pos)

    def _show_add_dialog(self) -> None:
        dialog = IncomeFormDialog(
            self._income_service,
            self._student_service,
            self._class_service,
            parent=self
        )
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_edit_dialog(self, income_id: int) -> None:
        dialog = IncomeFormDialog(
            self._income_service,
            self._student_service,
            self._class_service,
            income_id=income_id,
            parent=self
        )
        if dialog.exec() == IncomeFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_detail_dialog(self, income_id: int) -> None:
        dialog = IncomeDetailDialog(self._income_service, income_id, parent=self)
        dialog.exec()

    def _delete_income(self, income_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this income record? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._income_service.delete_income(income_id)
                self.refresh()
            except Exception as e:
                logger.exception("Delete failed")
                QMessageBox.critical(self, "Error", str(e))

    def _clear_filters(self) -> None:
        self.search_bar.set_text("")
        self.type_combo.setCurrentIndex(0)
        self.method_combo.setCurrentIndex(0)
        self.period_combo.setCurrentIndex(0)
        self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
        self.date_to_edit.setDate(QDate.currentDate())
        self._apply_filters()