# -*- coding: utf-8 -*-
"""
FinanceDashboardPage - Real dashboard with KPIs and recent transactions.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QSizePolicy, QListWidget, QListWidgetItem
)

from centermanager.services.finance_dashboard_service import FinanceDashboardService
from centermanager.ui.shared import StatisticGrid, DataTable, EmptyState, LoadingWidget
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.design_system.components import SectionHeader
from centermanager.ui.shared import ChartCard
logger = logging.getLogger(__name__)


class FinanceDashboardPage(QWidget):
    def __init__(
        self,
        dashboard_service: FinanceDashboardService,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._service = dashboard_service
        self._setup_ui()
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self):
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
        container_layout.setContentsMargins(SPACING['lg'], SPACING['lg'], SPACING['lg'], SPACING['lg'])
        container_layout.setSpacing(SPACING['xl'])

        # ---- KPI Stats ----
        self.stats_grid = StatisticGrid()
        container_layout.addWidget(self.stats_grid)

        # ---- Recent Income ----
        income_section = QWidget()
        income_layout = QVBoxLayout(income_section)
        income_layout.setContentsMargins(0, 0, 0, 0)
        income_layout.setSpacing(SPACING['sm'])
        income_header = SectionHeader("Recent Income")
        income_layout.addWidget(income_header)

        self.income_table = DataTable([
            {"key": "payment_date", "label": "Date", "sortable": False},
            {"key": "student_name", "label": "Student", "sortable": False},
            {"key": "class_name", "label": "Class", "sortable": False},
            {"key": "income_type", "label": "Type", "sortable": False},
            {"key": "amount", "label": "Amount", "sortable": False},
            {"key": "payment_method", "label": "Method", "sortable": False},
        ], page_size=10)
        self.income_table.setMaximumHeight(300)
        income_layout.addWidget(self.income_table)
        container_layout.addWidget(income_section)
        #Load chart
        self.revenue_method_chart = ChartCard("Revenue by Payment Method (This Month)", "pie")
        container_layout.addWidget(self.revenue_method_chart)

        self.expense_method_chart = ChartCard("Expense by Payment Method (This Month)", "pie")
        container_layout.addWidget(self.expense_method_chart)
        # ---- Recent Expense ----
        expense_section = QWidget()
        expense_layout = QVBoxLayout(expense_section)
        expense_layout.setContentsMargins(0, 0, 0, 0)
        expense_layout.setSpacing(SPACING['sm'])
        expense_header = SectionHeader("Recent Expense")
        expense_layout.addWidget(expense_header)

        self.expense_table = DataTable([
            {"key": "payment_date", "label": "Date", "sortable": False},
            {"key": "category", "label": "Category", "sortable": False},
            {"key": "description", "label": "Description", "sortable": False},
            {"key": "amount", "label": "Amount", "sortable": False},
            {"key": "status", "label": "Status", "sortable": False},
        ], page_size=10)
        self.expense_table.setMaximumHeight(300)
        expense_layout.addWidget(self.expense_table)
        container_layout.addWidget(expense_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Loading overlay
        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def refresh(self):
        self.loading.setVisible(True)
        try:
            data = self._service.get_dashboard_data()
            self._update_kpis(data)
            self._update_income_table(data.get("recent_income", []))
            self._update_expense_table(data.get("recent_expense", []))
            
            # Cập nhật biểu đồ
            revenue_method = data.get("revenue_by_method_month", {})
            if revenue_method:
                chart_data = [(method, amount) for method, amount in revenue_method.items()]
                self.revenue_method_chart.set_data(chart_data)
            else:
                self.revenue_method_chart.set_data([("No data", 0)])
            
            expense_method = data.get("expense_by_method_month", {})
            if expense_method:
                chart_data2 = [(method, amount) for method, amount in expense_method.items()]
                self.expense_method_chart.set_data(chart_data2)
            else:
                self.expense_method_chart.set_data([("No data", 0)])
                
        except Exception as e:
            logger.exception("Failed to refresh finance dashboard")
            self._show_error()
        finally:
            self.loading.setVisible(False)

    def _update_kpis(self, data: dict):
        revenue_today = data.get("revenue_today", 0)
        revenue_month = data.get("revenue_month", 0)
        expense_today = data.get("expense_today", 0)
        expense_month = data.get("expense_month", 0)
        net_cash = data.get("net_cash_flow", 0)

        # Format currency (VND)
        def fmt(v):
            return f"{v:,.0f} VND"

        self.stats_grid.set_metrics([
            {"icon": "📈", "label": "Revenue Today", "value": fmt(revenue_today)},
            {"icon": "📊", "label": "Revenue This Month", "value": fmt(revenue_month)},
            {"icon": "📉", "label": "Expense Today", "value": fmt(expense_today)},
            {"icon": "📉", "label": "Expense This Month", "value": fmt(expense_month)},
            {"icon": "💰", "label": "Net Cash Flow (Month)", "value": fmt(net_cash)},
        ], columns=5)

    def _update_income_table(self, incomes: list):
        if not incomes:
            empty = EmptyState(
                icon="💰",
                title="No Income Records",
                description="No income transactions found."
            )
            # We set empty data
            self.income_table.set_data([], 0)
            return

        data = []
        for inc in incomes:
            data.append({
                "payment_date": inc.payment_date.strftime("%d/%m/%Y"),
                "student_name": inc.student.full_name if inc.student else "-",
                "class_name": inc.class_.name if inc.class_ else "-",
                "income_type": inc.income_type,
                "amount": f"{inc.amount:,.0f}",
                "payment_method": inc.payment_method,
            })
        self.income_table.set_data(data, len(data))

    def _update_expense_table(self, expenses: list):
        if not expenses:
            empty = EmptyState(
                icon="💸",
                title="No Expense Records",
                description="No expense transactions found."
            )
            self.expense_table.set_data([], 0)
            return

        data = []
        for exp in expenses:
            data.append({
                "payment_date": exp.payment_date.strftime("%d/%m/%Y"),
                "category": exp.category,
                "description": exp.description[:40] + ("..." if len(exp.description) > 40 else ""),
                "amount": f"{exp.amount:,.0f}",
                "status": exp.status,
            })
        self.expense_table.set_data(data, len(data))

    def _show_error(self):
        self.stats_grid.set_metrics([
            {"icon": "⚠️", "label": "Revenue Today", "value": "Error"},
            {"icon": "⚠️", "label": "Revenue Month", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Today", "value": "Error"},
            {"icon": "⚠️", "label": "Expense Month", "value": "Error"},
            {"icon": "⚠️", "label": "Net Cash Flow", "value": "Error"},
        ], columns=5)
        self.income_table.set_data([], 0)
        self.expense_table.set_data([], 0)
# go_to_income = Signal()
# go_to_expense = Signal()
# go_to_outstanding = Signal()
# income_selected = Signal(int)
# expense_selected = Signal(int)
# row_double_clicked.connect(self._on_income_row_double_clicked)
# row_double_clicked.connect(self._on_expense_row_double_clicked)
# total_outstanding = data.get("total_outstanding", 0)
# net_cash_month
# net_bank_month