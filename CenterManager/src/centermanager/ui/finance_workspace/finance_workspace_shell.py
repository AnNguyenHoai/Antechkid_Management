# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.outstanding_list_page import OutstandingListPage
from centermanager.core.current_user import get_current_user
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged


class FinanceWorkspaceShell(QWidget):
    go_home = Signal()
    student_selected = Signal(int)

    def __init__(
        self,
        income_service,
        student_service,
        class_service,
        expense_service,
        dashboard_service,
        outstanding_service,
        platform_context=None,
        collaboration_manager=None,
        notification_service=None,
        event_bus: Optional[EventBus] = None,
        parent: Optional[QWidget] = None,
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
        self._notification_service = notification_service
        self._event_bus = event_bus or EventBus()
        self._authorized = False

        # Finance events must be active even while MainWindow wiring is being
        # migrated. When a shared app bus is supplied, this uses that bus.
        if getattr(self._income_service, "_event_bus", None) is None:
            self._income_service._event_bus = self._event_bus
        if hasattr(self._expense_service, "set_event_bus"):
            self._expense_service.set_event_bus(self._event_bus)

        self._setup_ui()
        self._connect_signals()
        self._event_bus.register(FinanceDataChanged, self._on_finance_data_changed)

        self._authorized = self._has_finance_access()
        if self._authorized:
            self.navigate_to("dashboard")
        else:
            self.nav.setEnabled(False)
            self.header.set_context("Finance Workspace", "Access restricted")

    def _has_finance_access(self) -> bool:
        try:
            user = get_current_user()
            return bool(user and (user.has_permission("finance.view") or user.is_admin))
        except Exception:
            return False

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = WorkspaceHeader("Finance Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout(); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "income", "icon": "📈", "label": "Income"},
            {"id": "expense", "icon": "📉", "label": "Expense"},
            {"id": "outstanding", "icon": "📋", "label": "Outstanding"},
        ]
        self.nav = WorkspaceNavigation("Finance Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget(); self.content_stack.setFrameShape(QFrame.Shape.NoFrame)
        self.dashboard_page = FinanceDashboardPage(self._dashboard_service); self.content_stack.addWidget(self.dashboard_page)
        self.income_page = IncomeListPage(self._income_service, self._student_service, self._class_service,
                                          self._collaboration_manager, self._notification_service); self.content_stack.addWidget(self.income_page)
        self.expense_page = ExpenseListPage(self._expense_service, self._collaboration_manager,
                                            self._notification_service); self.content_stack.addWidget(self.expense_page)
        self.outstanding_page = OutstandingListPage(self._outstanding_service, self._collaboration_manager,
                                                    self._notification_service); self.content_stack.addWidget(self.outstanding_page)
        body.addWidget(self.content_stack, 1); layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.dashboard_page.income_selected.connect(self._open_income_from_dashboard)
        self.dashboard_page.expense_selected.connect(self._open_expense_from_dashboard)
        self.outstanding_page.student_selected.connect(self.student_selected.emit)

    def _on_finance_data_changed(self, _event: FinanceDataChanged) -> None:
        if not self._has_finance_access():
            return
        # Finance totals, transaction lists and outstanding balances are
        # mutually dependent, so refresh all four projections after mutation.
        self.dashboard_page.refresh()
        self.income_page.refresh()
        self.expense_page.refresh()
        self.outstanding_page.refresh()

    def _open_income_from_dashboard(self, income_id: int) -> None:
        self.navigate_to("income")
        self.income_page._show_detail_dialog(income_id)

    def _open_expense_from_dashboard(self, expense_id: int) -> None:
        self.navigate_to("expense")
        self.expense_page._show_detail_dialog(expense_id)

    def navigate_to(self, page_id: str) -> None:
        self._authorized = self._has_finance_access()
        if not self._authorized:
            return
        pages = {
            "dashboard": (self.dashboard_page, "Dashboard"),
            "income": (self.income_page, "Income"),
            "expense": (self.expense_page, "Expense"),
            "outstanding": (self.outstanding_page, "Outstanding"),
        }
        target = pages.get(page_id)
        if target is None:
            return
        page, title = target
        self.content_stack.setCurrentWidget(page)
        self.nav.set_active_page(page_id)
        self.header.set_context("Finance Workspace", title)
        page.refresh()

    def refresh(self) -> None:
        if not self._has_finance_access():
            return
        current = self.content_stack.currentWidget()
        if current is not None and hasattr(current, "refresh"):
            current.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        self.income_page.set_write_enabled(enabled)
        self.expense_page.set_write_enabled(enabled)
