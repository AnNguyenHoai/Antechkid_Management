# -*- coding: utf-8 -*-
"""Finance dashboard with FinancePeriod-aware KPIs and transaction drill-down."""
import logging
from calendar import month_name
from datetime import date
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QLabel,
    QComboBox,
)

from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.ui.shared import StatisticGrid, DataTable, LoadingWidget, ChartCard
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.design_system.components import SectionHeader

logger = logging.getLogger(__name__)


class FinanceDashboardPage(QWidget):
    """Read-only Finance overview with selectable month/year Finance period context."""

    income_selected = Signal(int)
    expense_selected = Signal(int)

    def __init__(
        self,
        dashboard_service: FinanceDashboardService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = dashboard_service
        self._income_ids: list[int] = []
        self._expense_ids: list[int] = []
        self._selector_ready = False
        self._setup_ui()
        self._selector_ready = True

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {COLORS['background']};")

        container = QWidget()
        container.setStyleSheet(f"background: {COLORS['background']};")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(
            SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg']
        )
        container_layout.setSpacing(SPACING['xl'])

        selector_row = QHBoxLayout()
        selector_row.setSpacing(SPACING['sm'])
        selector_row.addWidget(QLabel("Finance period:"))

        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(month_name[month], month)
        selector_row.addWidget(self.month_combo)

        self.year_combo = QComboBox()
        current_year = date.today().year
        for year in range(current_year - 5, current_year + 2):
            self.year_combo.addItem(str(year), year)
        selector_row.addWidget(self.year_combo)

        self.period_label = QLabel("")
        self.period_label.setStyleSheet(f"color: {COLORS['text_secondary']};")
        selector_row.addWidget(self.period_label)
        selector_row.addStretch()
        container_layout.addLayout(selector_row)

        today = date.today()
        self.month_combo.setCurrentIndex(today.month - 1)
        year_index = self.year_combo.findData(today.year)
        if year_index >= 0:
            self.year_combo.setCurrentIndex(year_index)
        self.month_combo.currentIndexChanged.connect(self._on_period_selection_changed)
        self.year_combo.currentIndexChanged.connect(self._on_period_selection_changed)

        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        income_section = QWidget()
        income_layout = QVBoxLayout(income_section)
        income_layout.setContentsMargins(0, 0, 0, 0)
        income_layout.setSpacing(SPACING['sm'])
        income_layout.addWidget(SectionHeader("Recent Income in Selected Period"))
        self.income_table = DataTable([
            {"key": "payment_date", "label": "Date", "sortable": False},
            {"key": "student_name", "label": "Student", "sortable": False},
            {"key": "class_name", "label": "Class", "sortable": False},
            {"key": "income_type", "label": "Type", "sortable": False},
            {"key": "amount", "label": "Amount", "sortable": False},
            {"key": "payment_method", "label": "Method", "sortable": False},
        ], page_size=10)
        self.income_table.setMaximumHeight(300)
        self.income_table.row_double_clicked.connect(self._on_income_row_double_clicked)
        income_layout.addWidget(self.income_table)
        container_layout.addWidget(income_section)

        self.revenue_method_chart = ChartCard("Revenue by Payment Method (Selected Period)", "pie")
        container_layout.addWidget(self.revenue_method_chart)

        self.expense_method_chart = ChartCard("Expense by Payment Method (Selected Period)", "pie")
        container_layout.addWidget(self.expense_method_chart)

        expense_section = QWidget()
        expense_layout = QVBoxLayout(expense_section)
        expense_layout.setContentsMargins(0, 0, 0, 0)
        expense_layout.setSpacing(SPACING['sm'])
        expense_layout.addWidget(SectionHeader("Recent Expense in Selected Period"))
        self.expense_table = DataTable([
            {"key": "payment_date", "label": "Date", "sortable": False},
            {"key": "category", "label": "Category", "sortable": False},
            {"key": "description", "label": "Description", "sortable": False},
            {"key": "amount", "label": "Amount", "sortable": False},
            {"key": "status", "label": "Status", "sortable": False},
        ], page_size=10)
        self.expense_table.setMaximumHeight(300)
        self.expense_table.row_double_clicked.connect(self._on_expense_row_double_clicked)
        expense_layout.addWidget(self.expense_table)
        container_layout.addWidget(expense_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def _selected_target_date(self) -> date:
        month = self.month_combo.currentData() or date.today().month
        year = self.year_combo.currentData() or date.today().year
        # Month/year is only a navigation hint. The service resolves this date to
        # the canonical FinancePeriod bucket and returns the exact boundaries.
        return date(int(year), int(month), 1)

    def _on_period_selection_changed(self, _index: int) -> None:
        if self._selector_ready:
            self.refresh()

    def refresh(self) -> None:
        self.loading.setVisible(True)
        try:
            data = self._service.get_dashboard_data(
                target_date=self._selected_target_date()
            )
            self.period_label.setText(data.get("period_label", ""))
            self._update_kpis(data)
            self._update_income_table(data.get("recent_income", []))
            self._update_expense_table(data.get("recent_expense", []))

            revenue_method = data.get("revenue_by_method_period", {})
            self.revenue_method_chart.set_data(
                list(revenue_method.items()) if revenue_method else [("No data", 0)]
            )
            expense_method = data.get("expense_by_method_period", {})
            self.expense_method_chart.set_data(
                list(expense_method.items()) if expense_method else [("No data", 0)]
            )
        except Exception:
            logger.exception("Failed to refresh finance dashboard")
            self._show_error()
        finally:
            self.loading.setVisible(False)

    def _update_kpis(self, data: dict) -> None:
        def fmt_money(value):
            return f"{value:,.0f} VND"

        self.stats_grid.set_metrics([
            {"icon": "📈", "label": "Revenue Today", "value": fmt_money(data.get("revenue_today", 0))},
            {"icon": "📊", "label": "Revenue Selected Period", "value": fmt_money(data.get("revenue_period", 0))},
            {"icon": "📉", "label": "Expense Today", "value": fmt_money(data.get("expense_today", 0))},
            {"icon": "📉", "label": "Expense Selected Period", "value": fmt_money(data.get("expense_period", 0))},
            {"icon": "💰", "label": "Net Cash Flow (Period)", "value": fmt_money(data.get("net_cash_flow", 0))},
            {"icon": "🧾", "label": "Outstanding Tuition", "value": fmt_money(data.get("total_outstanding", 0))},
            {"icon": "👥", "label": "Students With Debt", "value": str(data.get("students_with_debt", 0))},
            {"icon": "⚠️", "label": "Tuition Not Configured", "value": str(data.get("unconfigured_tuition_count", 0))},
        ], columns=4)

    def _update_income_table(self, incomes: list) -> None:
        self._income_ids = [income.id for income in incomes]
        data = [{
            "payment_date": inc.payment_date.strftime("%d/%m/%Y"),
            "student_name": inc.student.full_name if inc.student else "-",
            "class_name": inc.class_.name if inc.class_ else "-",
            "income_type": inc.income_type,
            "amount": f"{inc.amount:,.0f}",
            "payment_method": inc.payment_method,
        } for inc in incomes]
        self.income_table.set_data(data, len(data))

    def _update_expense_table(self, expenses: list) -> None:
        self._expense_ids = [expense.id for expense in expenses]
        data = [{
            "payment_date": exp.payment_date.strftime("%d/%m/%Y"),
            "category": exp.category,
            "description": exp.description[:40] + ("..." if len(exp.description) > 40 else ""),
            "amount": f"{exp.amount:,.0f}",
            "status": exp.status,
        } for exp in expenses]
        self.expense_table.set_data(data, len(data))

    def _on_income_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._income_ids):
            self.income_selected.emit(self._income_ids[row])

    def _on_expense_row_double_clicked(self, row: int) -> None:
        if 0 <= row < len(self._expense_ids):
            self.expense_selected.emit(self._expense_ids[row])

    def _show_error(self) -> None:
        self._income_ids = []
        self._expense_ids = []
        self.period_label.setText("Unable to resolve Finance period")
        self.stats_grid.set_metrics([
            {"icon": "⚠️", "label": "Revenue Today", "value": "Error"},
            {"icon": "⚠️", "label": "Revenue Selected Period", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Today", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Selected Period", "value": "Error"},
            {"icon": "⚠️", "label": "Net Cash Flow (Period)", "value": "Error"},
            {"icon": "⚠️", "label": "Outstanding Tuition", "value": "Error"},
            {"icon": "⚠️", "label": "Students With Debt", "value": "Error"},
            {"icon": "⚠️", "label": "Tuition Not Configured", "value": "Error"},
        ], columns=4)
        self.income_table.set_data([], 0)
        self.expense_table.set_data([], 0)
