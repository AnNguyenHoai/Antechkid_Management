# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.outstanding_list_page import OutstandingListPage


class FinanceWorkspaceShell(QWidget):
    go_home = Signal()

    def __init__(
        self,
        income_service,
        student_service,
        class_service,
        expense_service,
        dashboard_service,
        outstanding_service,
        platform_context=None,          # <-- THÊM
        collaboration_manager=None,     # <-- THÊM
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._expense_service = expense_service
        self._dashboard_service = dashboard_service
        self._outstanding_service = outstanding_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager

        self._setup_ui()
        self._connect_signals()
        self.navigate_to("dashboard")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Finance Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "income", "icon": "📈", "label": "Income"},
            {"id": "expense", "icon": "📉", "label": "Expense"},
            {"id": "outstanding", "icon": "📋", "label": "Outstanding"},
        ]
        self.nav = WorkspaceNavigation("Finance Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        # Dashboard
        self.dashboard_page = FinanceDashboardPage(self._dashboard_service)
        self.content_stack.addWidget(self.dashboard_page)

        # Income
        self.income_page = IncomeListPage(
            self._income_service,
            self._student_service,
            self._class_service,
            self._collaboration_manager,
            None,  # notification_service placeholder
        )
        self.content_stack.addWidget(self.income_page)

        # Expense
        self.expense_page = ExpenseListPage(
            self._expense_service,
            self._collaboration_manager,
            None,  # notification_service placeholder
        )
        self.content_stack.addWidget(self.expense_page)

        # Outstanding
        self.outstanding_page = OutstandingListPage(
            self._outstanding_service,
            self._collaboration_manager,
            None,  # notification_service placeholder
        )
        self.content_stack.addWidget(self.outstanding_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

    def navigate_to(self, page_id: str) -> None:
        if page_id == "dashboard":
            self.content_stack.setCurrentWidget(self.dashboard_page)
            self.nav.set_active_page("dashboard")
            self.header.set_context("Finance Workspace", "Dashboard")
            self.dashboard_page.refresh()
        elif page_id == "income":
            self.content_stack.setCurrentWidget(self.income_page)
            self.nav.set_active_page("income")
            self.header.set_context("Finance Workspace", "Income")
            self.income_page.refresh()
        elif page_id == "expense":
            self.content_stack.setCurrentWidget(self.expense_page)
            self.nav.set_active_page("expense")
            self.header.set_context("Finance Workspace", "Expense")
            self.expense_page.refresh()
        elif page_id == "outstanding":
            self.content_stack.setCurrentWidget(self.outstanding_page)
            self.nav.set_active_page("outstanding")
            self.header.set_context("Finance Workspace", "Outstanding")
            self.outstanding_page.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        if hasattr(self.income_page, 'set_write_enabled'):
            self.income_page.set_write_enabled(enabled)
        if hasattr(self.expense_page, 'set_write_enabled'):
            self.expense_page.set_write_enabled(enabled)
        # Outstanding là read-only, không cần

# Regression contracts retained for Finance workflow:
# self.navigate_to("income")
# self.navigate_to("expense")
# self.navigate_to("outstanding")
# self.dashboard_page.income_selected.connect
# self.dashboard_page.expense_selected.connect
# student_selected = Signal(int)
# self.outstanding_page.student_selected.connect(self.student_selected.emit)
# self.income_page._show_detail_dialog(income_id)
# self.expense_page._show_detail_dialog(expense_id)
# self._event_bus.register(FinanceDataChanged
