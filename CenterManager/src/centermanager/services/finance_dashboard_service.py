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

    def __init__(self, income_service: IncomeService, expense_service: ExpenseService, outstanding_service=None):
        self._income_service = income_service
        self._expense_service = expense_service
        self._outstanding_service = outstanding_service
        self._outstanding_service = outstanding_service

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
    def get_revenue_by_payment_method(self, date_from: date, date_to: date) -> Dict[str, float]:
        """Return revenue breakdown by payment method."""
        incomes, _ = self._income_service.list_incomes(
            date_from=date_from,
            date_to=date_to,
            page=1,
            per_page=10000
        )
        result = {}
        for inc in incomes:
            method = inc.payment_method or "Other"
            result[method] = result.get(method, 0.0) + inc.amount
        return {"Cash": result.get("Cash", 0), "Bank": result.get("Bank", result.get("Bank Transfer", 0)), "Other": result.get("Other", 0)}

    def get_expense_by_payment_method(self, date_from: date, date_to: date) -> Dict[str, float]:
        """Return expense breakdown by payment method."""
        expenses, _ = self._expense_service.list_expenses(
            date_from=date_from,
            date_to=date_to,
            page=1,
            per_page=10000
        )
        result = {}
        for exp in expenses:
            method = exp.payment_method or "Other"
            result[method] = result.get(method, 0.0) + exp.amount
        return {"Cash": result.get("Cash", 0), "Bank": result.get("Bank", result.get("Bank Transfer", 0)), "Other": result.get("Other", 0)}

    def get_dashboard_data(self) -> Dict[str, Any]:
        today = self._get_today_date()
        start_month = self._get_first_day_of_month()
        return {
            "revenue_today": self.get_revenue_today(),
            "revenue_month": self.get_revenue_this_month(),
            "expense_today": self.get_expense_today(),
            "expense_month": self.get_expense_this_month(),
            "net_cash_flow": self.get_net_cash_flow(),
            "recent_income": self.get_recent_income(),
            "recent_expense": self.get_recent_expense(),
            "revenue_by_method_month": self.get_revenue_by_payment_method(start_month, today),
            "expense_by_method_month": self.get_expense_by_payment_method(start_month, today),
        }
    @staticmethod
    def _normalize_payment_method(value):
        mapping = {"Bank Transfer": "Bank", "Bank": "Bank", "Cash": "Cash", "Other": "Other"}
        return mapping.get(value, "Other")

    def get_dashboard_snapshot(self):
        from types import SimpleNamespace
        today = date.today()
        revenue = self.get_revenue_by_payment_method(today, today)
        expense = self.get_expense_by_payment_method(today, today)
        stats = self._outstanding_service.get_outstanding_stats() if self._outstanding_service else {}
        return SimpleNamespace(
            cash_in_month=revenue.get("Cash", 0),
            bank_in_month=revenue.get("Bank", 0),
            cash_out_month=expense.get("Cash", 0),
            bank_out_month=expense.get("Bank", 0),
            net_cash_month=revenue.get("Cash", 0) - expense.get("Cash", 0),
            net_bank_month=revenue.get("Bank", 0) - expense.get("Bank", 0),
            total_outstanding=stats.get("total_outstanding", 0),
            students_with_debt=stats.get("total_students_with_debt", 0),
            unconfigured_tuition_count=stats.get("total_unconfigured_tuition", 0),
        )
