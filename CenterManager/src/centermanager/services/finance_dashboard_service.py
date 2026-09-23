# -*- coding: utf-8 -*-
"""
FinanceDashboardService - Read-only aggregation service for Finance Dashboard.
"""
import logging
from datetime import date
from typing import Dict, List, Any, Optional, Tuple

from centermanager.services.income_service import IncomeService
from centermanager.services.expense_service import ExpenseService
from centermanager.models.income import Income
from centermanager.models.expense import Expense

logger = logging.getLogger(__name__)


class FinanceDashboardService:
    """Aggregate financial data for dashboard. Read-only and FinancePeriod-aware."""

    def __init__(
        self,
        income_service: IncomeService,
        expense_service: ExpenseService,
        outstanding_service=None,
        finance_period_service=None,
    ):
        self._income_service = income_service
        self._expense_service = expense_service
        self._outstanding_service = outstanding_service

        # Production composition historically constructs this service with only
        # Income/Expense/Outstanding. Preserve that public constructor while
        # adopting FinancePeriod as the dashboard source of truth. Explicit DI
        # still wins for tests and future composition-root cleanup.
        if finance_period_service is None:
            session_factory = getattr(income_service, "_session_factory", None)
            if session_factory is not None:
                from centermanager.services.finance_period_service import FinancePeriodService
                finance_period_service = FinancePeriodService(session_factory)
        self._finance_period_service = finance_period_service

    def _get_today_date(self) -> date:
        return date.today()

    def _get_first_day_of_month(self) -> date:
        today = self._get_today_date()
        return date(today.year, today.month, 1)

    def _resolve_dashboard_period(
        self,
        target_date: Optional[date] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        period_configured: Optional[bool] = None,
    ) -> Optional[Tuple[date, date, date]]:
        """Resolve canonical period bounds and the last date used for live cash data.

        FinanceWorkspaceShell owns the shared period. Explicit bounds supplied by
        the shell always win, preventing Dashboard from independently resolving a
        different period. The legacy resolver remains for older/lightweight callers.
        """
        today = self._get_today_date()
        target = target_date or today

        if period_configured is False:
            return None

        if period_start is not None and period_end is not None:
            query_end = today if period_start <= today <= period_end else period_end
            return period_start, period_end, query_end

        if self._finance_period_service is None:
            start = date(today.year, today.month, 1)
            return start, today, today

        config = self._finance_period_service.get_active_period(target)
        if config is None:
            return None

        start, end = self._finance_period_service.get_period_bounds(
            config.effective_from,
            target,
            config.duration_months,
            config.effective_to,
        )
        query_end = today if start <= today <= end else end
        return start, end, query_end

    def _get_outstanding_stats(
        self,
        period_start: Optional[date] = None,
        target_date: Optional[date] = None,
        force_period: bool = False,
    ) -> Dict[str, int]:
        if self._outstanding_service is None:
            return {}
        # Older/lightweight dashboard callers have no FinancePeriodService and
        # historically expose a no-argument Outstanding API. Preserve that path.
        if period_start is None or (
            self._finance_period_service is None and not force_period
        ):
            return self._outstanding_service.get_outstanding_stats()
        return self._outstanding_service.get_outstanding_stats(
            period_start=period_start,
            on_date=target_date,
        )

    @staticmethod
    def _empty_payment_methods() -> Dict[str, float]:
        return {"Cash": 0.0, "Bank": 0.0, "Other": 0.0}

    @staticmethod
    def _period_label(period_start: date, period_end: date) -> str:
        return f"{period_start:%d/%m/%Y} - {period_end:%d/%m/%Y}"

    @staticmethod
    def _build_cash_vs_bank(
        revenue_by_method: Dict[str, float],
        expense_by_method: Dict[str, float],
    ) -> Dict[str, Dict[str, float]]:
        """Return service-owned Cash/Bank inflow, outflow and net comparison."""
        cash_income = float(revenue_by_method.get("Cash", 0.0))
        cash_expense = float(expense_by_method.get("Cash", 0.0))
        bank_income = float(revenue_by_method.get("Bank", 0.0))
        bank_expense = float(expense_by_method.get("Bank", 0.0))
        return {
            "Cash": {
                "income": cash_income,
                "expense": cash_expense,
                "net": cash_income - cash_expense,
            },
            "Bank": {
                "income": bank_income,
                "expense": bank_expense,
                "net": bank_income - bank_expense,
            },
        }

    # ---- Revenue ----

    def get_revenue_today(self) -> float:
        today = self._get_today_date()
        incomes, _ = self._income_service.list_incomes(
            date_from=today, date_to=today, page=1, per_page=10000
        )
        return sum(i.amount for i in incomes)

    def get_revenue_this_month(self) -> float:
        start = self._get_first_day_of_month()
        end = self._get_today_date()
        incomes, _ = self._income_service.list_incomes(
            date_from=start, date_to=end, page=1, per_page=10000
        )
        return sum(i.amount for i in incomes)

    # ---- Expense ----

    def get_expense_today(self) -> float:
        today = self._get_today_date()
        expenses, _ = self._expense_service.list_expenses(
            date_from=today,
            date_to=today,
            page=1,
            per_page=10000,
            realized_only=True,
        )
        return sum(e.amount for e in expenses)

    def get_expense_this_month(self) -> float:
        start = self._get_first_day_of_month()
        end = self._get_today_date()
        expenses, _ = self._expense_service.list_expenses(
            date_from=start,
            date_to=end,
            page=1,
            per_page=10000,
            realized_only=True,
        )
        return sum(e.amount for e in expenses)

    # ---- Cash Flow ----

    def get_net_cash_flow(self) -> float:
        return self.get_revenue_this_month() - self.get_expense_this_month()

    # ---- Recent Transactions ----

    def get_recent_income(self, limit: int = 10) -> List[Income]:
        incomes, _ = self._income_service.list_incomes(page=1, per_page=limit)
        return incomes

    def get_recent_expense(self, limit: int = 10) -> List[Expense]:
        expenses, _ = self._expense_service.list_expenses(page=1, per_page=limit)
        return expenses

    def _get_recent_income_for_period(
        self, period_start: date, query_end: date, limit: int = 10
    ) -> List[Income]:
        incomes, _ = self._income_service.list_incomes(
            finance_period_start=period_start,
            date_from=period_start,
            date_to=query_end,
            page=1,
            per_page=limit,
        )
        return incomes

    def _get_recent_expense_for_period(
        self, period_start: date, query_end: date, limit: int = 10
    ) -> List[Expense]:
        expenses, _ = self._expense_service.list_expenses(
            finance_period_start=period_start,
            date_from=period_start,
            date_to=query_end,
            page=1,
            per_page=limit,
        )
        return expenses

    # ---- Aggregated Dashboard Data ----

    def get_revenue_by_payment_method(
        self,
        date_from: date,
        date_to: date,
        finance_period_start: Optional[date] = None,
    ) -> Dict[str, float]:
        kwargs = dict(
            date_from=date_from,
            date_to=date_to,
            page=1,
            per_page=10000,
        )
        if finance_period_start is not None:
            kwargs["finance_period_start"] = finance_period_start
        incomes, _ = self._income_service.list_incomes(**kwargs)
        result: Dict[str, float] = {}
        for inc in incomes:
            method = self._normalize_payment_method(inc.payment_method)
            result[method] = result.get(method, 0.0) + inc.amount
        return {
            "Cash": result.get("Cash", 0.0),
            "Bank": result.get("Bank", 0.0),
            "Other": result.get("Other", 0.0),
        }

    def get_expense_by_payment_method(
        self,
        date_from: date,
        date_to: date,
        finance_period_start: Optional[date] = None,
    ) -> Dict[str, float]:
        expenses, _ = self._expense_service.list_expenses(
            finance_period_start=finance_period_start,
            date_from=date_from,
            date_to=date_to,
            page=1,
            per_page=10000,
            realized_only=True,
        )
        result: Dict[str, float] = {}
        for exp in expenses:
            method = self._normalize_payment_method(exp.payment_method)
            result[method] = result.get(method, 0.0) + exp.amount
        return {
            "Cash": result.get("Cash", 0.0),
            "Bank": result.get("Bank", 0.0),
            "Other": result.get("Other", 0.0),
        }

    def get_dashboard_data(
        self,
        target_date: Optional[date] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        period_configured: Optional[bool] = None,
    ) -> Dict[str, Any]:
        today = self._get_today_date()
        target = target_date or today
        period = self._resolve_dashboard_period(
            target,
            period_start=period_start,
            period_end=period_end,
            period_configured=period_configured,
        )

        if period is None:
            empty_methods = self._empty_payment_methods()
            return {
                "period_configured": False,
                "period_start": None,
                "period_end": None,
                "period_label": "Finance period not configured",
                "selected_target_date": target,
                "revenue_today": self.get_revenue_today(),
                "revenue_period": 0,
                "revenue_month": 0,
                "expense_today": self.get_expense_today(),
                "expense_period": 0,
                "expense_month": 0,
                "net_cash_flow": 0,
                "recent_income": [],
                "recent_expense": [],
                "revenue_by_method_period": dict(empty_methods),
                "expense_by_method_period": dict(empty_methods),
                "revenue_by_method_month": dict(empty_methods),
                "expense_by_method_month": dict(empty_methods),
                "cash_vs_bank": self._build_cash_vs_bank(empty_methods, empty_methods),
                "total_outstanding": 0,
                "students_with_debt": 0,
                "unconfigured_tuition_count": 0,
            }

        resolved_period_start, resolved_period_end, query_end = period
        revenue_by_method = self.get_revenue_by_payment_method(
            resolved_period_start,
            query_end,
            finance_period_start=resolved_period_start,
        )
        expense_by_method = self.get_expense_by_payment_method(
            resolved_period_start,
            query_end,
            finance_period_start=resolved_period_start,
        )
        revenue_period = sum(revenue_by_method.values())
        expense_period = sum(expense_by_method.values())
        stats = self._get_outstanding_stats(
            resolved_period_start,
            target,
            force_period=period_start is not None,
        )

        # When an explicit shared period is supplied it is authoritative even if
        # this service was constructed without FinancePeriodService.
        if self._finance_period_service is None and period_start is None:
            recent_income = self.get_recent_income()
            recent_expense = self.get_recent_expense()
        else:
            recent_income = self._get_recent_income_for_period(
                resolved_period_start, query_end
            )
            recent_expense = self._get_recent_expense_for_period(
                resolved_period_start, query_end
            )

        return {
            "period_configured": True,
            "period_start": resolved_period_start,
            "period_end": resolved_period_end,
            "period_label": self._period_label(
                resolved_period_start, resolved_period_end
            ),
            "selected_target_date": target,
            "revenue_today": self.get_revenue_today(),
            "revenue_period": revenue_period,
            "revenue_month": revenue_period,
            "expense_today": self.get_expense_today(),
            "expense_period": expense_period,
            "expense_month": expense_period,
            "net_cash_flow": revenue_period - expense_period,
            "recent_income": recent_income,
            "recent_expense": recent_expense,
            "revenue_by_method_period": revenue_by_method,
            "expense_by_method_period": expense_by_method,
            "revenue_by_method_month": revenue_by_method,
            "expense_by_method_month": expense_by_method,
            "cash_vs_bank": self._build_cash_vs_bank(
                revenue_by_method, expense_by_method
            ),
            "total_outstanding": stats.get("total_outstanding", 0),
            "students_with_debt": stats.get("total_students_with_debt", 0),
            "unconfigured_tuition_count": stats.get("total_unconfigured_tuition", 0),
        }

    @staticmethod
    def _normalize_payment_method(value):
        mapping = {
            "Bank Transfer": "Bank",
            "Bank": "Bank",
            "Cash": "Cash",
            "Other": "Other",
            "TÀI KHOẢN CÁ NHÂN": "Cash",
            "TÀI KHOẢN CÔNG TY": "Bank",
        }
        return mapping.get(value, "Other")

    def get_dashboard_snapshot(self, target_date: Optional[date] = None):
        """Backward-compatible snapshot API used by older dashboard callers/tests."""
        from types import SimpleNamespace

        target = target_date or self._get_today_date()
        period = self._resolve_dashboard_period(target)
        if period is None:
            return SimpleNamespace(
                cash_in_month=0,
                bank_in_month=0,
                cash_out_month=0,
                bank_out_month=0,
                net_cash_month=0,
                net_bank_month=0,
                total_outstanding=0,
                students_with_debt=0,
                unconfigured_tuition_count=0,
                period_start=None,
                period_end=None,
                period_configured=False,
            )

        resolved_period_start, resolved_period_end, query_end = period
        revenue = self.get_revenue_by_payment_method(
            resolved_period_start,
            query_end,
            finance_period_start=(
                resolved_period_start
                if self._finance_period_service is not None
                else None
            ),
        )
        expense = self.get_expense_by_payment_method(
            resolved_period_start,
            query_end,
            finance_period_start=(
                resolved_period_start
                if self._finance_period_service is not None
                else None
            ),
        )
        stats = self._get_outstanding_stats(resolved_period_start, target)
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
            period_start=resolved_period_start,
            period_end=resolved_period_end,
            period_configured=True,
        )
