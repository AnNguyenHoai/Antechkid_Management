# -*- coding: utf-8 -*-
"""Finance Workspace UI components."""
from .finance_workspace_shell import FinanceWorkspaceShell
from .finance_dashboard_page import FinanceDashboardPage
from .income_list_page import IncomeListPage
from .income_form_dialog import IncomeFormDialog
from .income_detail_dialog import IncomeDetailDialog
from .collect_tuition_dialog import CollectTuitionDialog
from .expense_list_page import ExpenseListPage
from .expense_form_dialog import ExpenseFormDialog
from .expense_detail_dialog import ExpenseDetailDialog
from .outstanding_list_page import OutstandingListPage

__all__ = [
    "FinanceWorkspaceShell",
    "FinanceDashboardPage",
    "IncomeListPage",
    "IncomeFormDialog",
    "IncomeDetailDialog",
    "StudentFinancialWidget",
    "CollectTuitionDialog",
]