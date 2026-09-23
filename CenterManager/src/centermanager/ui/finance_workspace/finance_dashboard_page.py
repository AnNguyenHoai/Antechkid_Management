# -*- coding: utf-8 -*-
"""Finance dashboard with FinancePeriod-aware KPIs and transaction drill-down."""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QFrame,
    QPushButton,
)

from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.ui.shared import StatisticGrid, DataTable, LoadingWidget, ChartCard
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.design_system.components import SectionHeader

logger = logging.getLogger(__name__)


class FinanceDashboardPage(QWidget):
    """Read-only Finance overview driven by the workspace shared period."""

    income_selected = Signal(int)
    expense_selected = Signal(int)
    drilldown_requested = Signal(str)

    def __init__(
        self,
        dashboard_service: FinanceDashboardService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = dashboard_service
        self._income_ids: list[int] = []
        self._expense_ids: list[int] = []
        self._target_date = date.today()
        self._period_start: Optional[date] = None
        self._period_end: Optional[date] = None
        self._period_configured: Optional[bool] = None
        self._setup_ui()

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

        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        drilldown_row = QHBoxLayout()
        drilldown_row.setSpacing(SPACING['sm'])
        for label, page_id in (
            ("View Income", "income"),
            ("View Expense", "expense"),
            ("View Outstanding", "outstanding"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, target=page_id: self.drilldown_requested.emit(target)
            )
            drilldown_row.addWidget(button)
        drilldown_row.addStretch()
        container_layout.addLayout(drilldown_row)

        self.cash_vs_bank_chart = ChartCard(
            "Cash vs Bank - Inflow / Outflow (Selected Period)", "bar"
        )
        container_layout.addWidget(self.cash_vs_bank_chart)

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

        self.revenue_method_chart = ChartCard(
            "Revenue by Payment Method (Selected Period)", "pie"
        )
        container_layout.addWidget(self.revenue_method_chart)

        self.expense_method_chart = ChartCard(
            "Expense by Payment Method (Selected Period)", "pie"
        )
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

    def refresh(
        self,
        target_date: Optional[date] = None,
        period_start=None,
        period_end=None,
        period_configured=None,
        **_kwargs,
    ) -> None:
        if target_date is not None:
            self._target_date = target_date
        self._period_start = period_start
        self._period_end = period_end
        self._period_configured = period_configured

        self.loading.setVisible(True)
        try:
            data = self._service.get_dashboard_data(
                target_date=self._target_date,
                period_start=self._period_start,
                period_end=self._period_end,
                period_configured=self._period_configured,
            )
            self._update_kpis(data)
            self._update_income_table(data.get("recent_income", []))
            self._update_expense_table(data.get("recent_expense", []))

            cash_vs_bank = data.get("cash_vs_bank", {})
            cash = cash_vs_bank.get("Cash", {})
            bank = cash_vs_bank.get("Bank", {})
            self.cash_vs_bank_chart.set_data([
                ("Cash In", cash.get("income", 0)),
                ("Cash Out", cash.get("expense", 0)),
                ("Bank In", bank.get("income", 0)),
                ("Bank Out", bank.get("expense", 0)),
            ])

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
            {"icon": "📊", "label": "Income Selected Period", "value": fmt_money(data.get("revenue_period", 0))},
            {"icon": "📉", "label": "Expense Selected Period", "value": fmt_money(data.get("expense_period", 0))},
            {"icon": "💰", "label": "Net Selected Period", "value": fmt_money(data.get("net_cash_flow", 0))},
            {"icon": "🧾", "label": "Outstanding Tuition", "value": fmt_money(data.get("total_outstanding", 0))},
            {"icon": "📈", "label": "Income Today", "value": fmt_money(data.get("revenue_today", 0))},
            {"icon": "📉", "label": "Expense Today", "value": fmt_money(data.get("expense_today", 0))},
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
        data = []
        for exp in expenses:
            description = exp.description or ""
            data.append({
                "payment_date": exp.payment_date.strftime("%d/%m/%Y"),
                "category": exp.category or "-",
                "description": description[:40] + ("..." if len(description) > 40 else ""),
                "amount": f"{exp.amount:,.0f}",
                "status": exp.status or "-",
            })
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
        self.stats_grid.set_metrics([
            {"icon": "⚠️", "label": "Income Selected Period", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Selected Period", "value": "Error"},
            {"icon": "⚠️", "label": "Net Selected Period", "value": "Error"},
            {"icon": "⚠️", "label": "Outstanding Tuition", "value": "Error"},
            {"icon": "⚠️", "label": "Income Today", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Today", "value": "Error"},
            {"icon": "⚠️", "label": "Students With Debt", "value": "Error"},
            {"icon": "⚠️", "label": "Tuition Not Configured", "value": "Error"},
        ], columns=4)
        self.cash_vs_bank_chart.set_data([])
        self.revenue_method_chart.set_data([])
        self.expense_method_chart.set_data([])
        self.income_table.set_data([], 0)
        self.expense_table.set_data([], 0)
