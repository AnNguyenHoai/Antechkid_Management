# -*- coding: utf-8 -*-
"""
FinanceWorkspaceShell - main shell for Finance Workspace.
"""
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
from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService


class FinanceWorkspaceShell(QWidget):
    go_home = Signal()

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
        self.dashboard_page = FinanceDashboardPage()
        self.content_stack.addWidget(self.dashboard_page)

        # Income - now real page
        self.income_page = IncomeListPage(
            self._income_service,
            self._student_service,
            self._class_service
        )
        self.content_stack.addWidget(self.income_page)

        # Expense (placeholder)
        from .finance_list_page import FinanceListPage
        self.expense_page = FinanceListPage("Expense")
        self.content_stack.addWidget(self.expense_page)

        # Outstanding (placeholder)
        self.outstanding_page = FinanceListPage("Outstanding")
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
        elif page_id == "income":
            self.content_stack.setCurrentWidget(self.income_page)
            self.nav.set_active_page("income")
            self.header.set_context("Finance Workspace", "Income")
            self.income_page.refresh()
        elif page_id == "expense":
            self.content_stack.setCurrentWidget(self.expense_page)
            self.nav.set_active_page("expense")
            self.header.set_context("Finance Workspace", "Expense")
        elif page_id == "outstanding":
            self.content_stack.setCurrentWidget(self.outstanding_page)
            self.nav.set_active_page("outstanding")
            self.header.set_context("Finance Workspace", "Outstanding")