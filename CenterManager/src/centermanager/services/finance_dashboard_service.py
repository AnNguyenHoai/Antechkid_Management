# -*- coding: utf-8 -*-
"""
FinanceDashboardService - Read-only aggregation service for Finance Dashboard.
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Tuple

from centermanager.services.income_service import IncomeService
from centermanager.services.expense_service import ExpenseService
from centermanager.models.income import Income
from centermanager.models.expense import Expense

logger = logging.getLogger(__name__)


class FinanceDashboardService:
    """Aggregate financial data for dashboard. Read-only."""

    def __init__(self, income_service: IncomeService, expense_service: ExpenseService):
        self._income_service = income_service
        self._expense_service = expense_service

    def _get_today_date(self) -> date:
        return date.today()

    def _get_first_day_of_month(self) -> date:
        today = self._get_today_date()
        return date(today.year, today.month, 1)

    # ---- Revenue ----

    def get_revenue_today(self) -> float:
        """Total income for today."""
        today = self._get_today_date()
        incomes, _ = self._income_service.list_incomes(
            date_from=today,
            date_to=today,
            page=1,
            per_page=10000  # get all
        )
        return sum(i.amount for i in incomes)

    def get_revenue_this_month(self) -> float:
        """Total income for current month."""
        start = self._get_first_day_of_month()
        end = self._get_today_date()
        incomes, _ = self._income_service.list_incomes(
            date_from=start,
            date_to=end,
            page=1,
            per_page=10000
        )
        return sum(i.amount for i in incomes)

    # ---- Expense ----

    def get_expense_today(self) -> float:
        """Total expense for today."""
        today = self._get_today_date()
        expenses, _ = self._expense_service.list_expenses(
            date_from=today,
            date_to=today,
            page=1,
            per_page=10000
        )
        return sum(e.amount for e in expenses)

    def get_expense_this_month(self) -> float:
        """Total expense for current month."""
        start = self._get_first_day_of_month()
        end = self._get_today_date()
        expenses, _ = self._expense_service.list_expenses(
            date_from=start,
            date_to=end,
            page=1,
            per_page=10000
        )
        return sum(e.amount for e in expenses)

    # ---- Cash Flow ----

    def get_net_cash_flow(self) -> float:
        """Net cash flow = Revenue - Expense."""
        revenue = self.get_revenue_this_month()
        expense = self.get_expense_this_month()
        return revenue - expense

    # ---- Recent Transactions ----

    def get_recent_income(self, limit: int = 10) -> List[Income]:
        """Get latest income records."""
        incomes, _ = self._income_service.list_incomes(
            page=1,
            per_page=limit
        )
        return incomes

    def get_recent_expense(self, limit: int = 10) -> List[Expense]:
        """Get latest expense records."""
        expenses, _ = self._expense_service.list_expenses(
            page=1,
            per_page=limit
        )
        return expenses

    # ---- Aggregated Dashboard Data ----

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Return all dashboard data in one call."""
        return {
            "revenue_today": self.get_revenue_today(),
            "revenue_month": self.get_revenue_this_month(),
            "expense_today": self.get_expense_today(),
            "expense_month": self.get_expense_this_month(),
            "net_cash_flow": self.get_net_cash_flow(),
            "recent_income": self.get_recent_income(),
            "recent_expense": self.get_recent_expense(),
        }