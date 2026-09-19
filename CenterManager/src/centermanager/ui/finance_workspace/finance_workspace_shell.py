# -*- coding: utf-8 -*-
from calendar import month_name
from datetime import date
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QFrame,
    QLabel,
    QComboBox,
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.outstanding_list_page import OutstandingListPage
from centermanager.ui.finance_workspace.financial_settlement_page import FinancialSettlementPage
from centermanager.core.current_user import get_current_user
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged


class FinanceWorkspaceShell(QWidget):
    """Single Finance workspace with one shared canonical FinancePeriod context."""

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
        settlement_service=None,
        finance_period_service=None,
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._expense_service = expense_service
        self._dashboard_service = dashboard_service
        self._outstanding_service = outstanding_service
        self._settlement_service = settlement_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._event_bus = event_bus or EventBus()
        self._authorized = False
        self._period_selector_ready = False

        # Reuse the dashboard's injected FinancePeriodService when available so
        # tests/composition roots keep one shared source of truth.
        self._finance_period_service = finance_period_service or getattr(
            self._dashboard_service, "_finance_period_service", None
        )
        if self._finance_period_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                from centermanager.services.finance_period_service import FinancePeriodService

                self._finance_period_service = FinancePeriodService(session_factory)

        # Compatibility construction keeps existing MainWindow/app call sites stable
        # while the service remains independently injectable for tests/new callers.
        if self._settlement_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                from centermanager.services.financial_settlement_service import FinancialSettlementService

                self._settlement_service = FinancialSettlementService(session_factory)

        # Finance events must be active even while MainWindow wiring is being
        # migrated. When a shared app bus is supplied, this uses that bus.
        if getattr(self._income_service, "_event_bus", None) is None:
            self._income_service._event_bus = self._event_bus
        if hasattr(self._expense_service, "set_event_bus"):
            self._expense_service.set_event_bus(self._event_bus)

        self._setup_ui()
        self._connect_signals()
        self._period_selector_ready = True
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

        # EP-FIN-05: one selector owns the period context for every Finance page.
        period_bar = QWidget()
        period_layout = QHBoxLayout(period_bar)
        period_layout.setContentsMargins(16, 8, 16, 8)
        period_layout.setSpacing(8)
        period_layout.addWidget(QLabel("Finance period:"))

        self.month_combo = QComboBox()
        for month in range(1, 13):
            self.month_combo.addItem(month_name[month], month)
        period_layout.addWidget(self.month_combo)

        self.year_combo = QComboBox()
        current_year = date.today().year
        for year in range(current_year - 5, current_year + 2):
            self.year_combo.addItem(str(year), year)
        period_layout.addWidget(self.year_combo)

        today = date.today()
        self.month_combo.setCurrentIndex(today.month - 1)
        year_index = self.year_combo.findData(today.year)
        if year_index >= 0:
            self.year_combo.setCurrentIndex(year_index)

        self.period_label = QLabel("")
        period_layout.addWidget(self.period_label)
        period_layout.addStretch()
        layout.addWidget(period_bar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "income", "icon": "📈", "label": "Income"},
            {"id": "expense", "icon": "📉", "label": "Expense"},
            {"id": "outstanding", "icon": "📋", "label": "Outstanding"},
            {"id": "settlement", "icon": "🧾", "label": "Settlement"},
        ]
        self.nav = WorkspaceNavigation("Finance Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)
        self.dashboard_page = FinanceDashboardPage(self._dashboard_service)
        self.content_stack.addWidget(self.dashboard_page)
        self.income_page = IncomeListPage(
            self._income_service,
            self._student_service,
            self._class_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.content_stack.addWidget(self.income_page)
        self.expense_page = ExpenseListPage(
            self._expense_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.content_stack.addWidget(self.expense_page)
        self.outstanding_page = OutstandingListPage(
            self._outstanding_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.content_stack.addWidget(self.outstanding_page)
        self.settlement_page = FinancialSettlementPage(
            self._settlement_service,
            self._notification_service,
        )
        self.content_stack.addWidget(self.settlement_page)
        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.dashboard_page.income_selected.connect(self._open_income_from_dashboard)
        self.dashboard_page.expense_selected.connect(self._open_expense_from_dashboard)
        self.dashboard_page.drilldown_requested.connect(self.navigate_to)
        self.outstanding_page.student_selected.connect(self.student_selected.emit)
        self.month_combo.currentIndexChanged.connect(self._on_period_selection_changed)
        self.year_combo.currentIndexChanged.connect(self._on_period_selection_changed)

    def _selected_target_date(self) -> date:
        month = self.month_combo.currentData() or date.today().month
        year = self.year_combo.currentData() or date.today().year
        return date(int(year), int(month), 1)

    def _resolve_shared_period(self):
        """Return target date plus canonical bounds for the shared selector."""
        target_date = self._selected_target_date()
        if self._finance_period_service is None:
            self.period_label.setText("Finance period service unavailable")
            return target_date, None, None, None

        try:
            config = self._finance_period_service.get_active_period(target_date)
            if config is None:
                self.period_label.setText("Finance period not configured")
                return target_date, None, None, False
            period_start, period_end = self._finance_period_service.get_period_bounds(
                config.effective_from,
                target_date,
                config.duration_months,
            )
            self.period_label.setText(
                f"{period_start:%d/%m/%Y} - {period_end:%d/%m/%Y}"
            )
            return target_date, period_start, period_end, True
        except Exception as exc:
            self.period_label.setText(f"Unable to resolve Finance period: {exc}")
            return target_date, None, None, False

    def _refresh_pages(self, pages) -> None:
        target_date, period_start, period_end, period_configured = self._resolve_shared_period()
        for page in pages:
            page.refresh(
                target_date=target_date,
                period_start=period_start,
                period_end=period_end,
                period_configured=period_configured,
            )

    def _refresh_page(self, page) -> None:
        self._refresh_pages([page])

    def _on_period_selection_changed(self, _index: int) -> None:
        if not self._period_selector_ready or not self._has_finance_access():
            return
        current = self.content_stack.currentWidget()
        if current is not None:
            self._refresh_page(current)

    def _on_finance_data_changed(self, _event: FinanceDataChanged) -> None:
        if not self._has_finance_access():
            return
        # All Finance surfaces are refreshed with exactly the same period context.
        self._refresh_pages([
            self.dashboard_page,
            self.income_page,
            self.expense_page,
            self.outstanding_page,
            self.settlement_page,
        ])

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
            "settlement": (self.settlement_page, "Settlement"),
        }
        target = pages.get(page_id)
        if target is None:
            return
        page, title = target
        self.content_stack.setCurrentWidget(page)
        self.nav.set_active_page(page_id)
        self.header.set_context("Finance Workspace", title)
        self._refresh_page(page)

    def refresh(self) -> None:
        if not self._has_finance_access():
            return
        current = self.content_stack.currentWidget()
        if current is not None:
            self._refresh_page(current)

    def set_write_enabled(self, enabled: bool) -> None:
        self.income_page.set_write_enabled(enabled)
        self.expense_page.set_write_enabled(enabled)
        self.settlement_page.set_write_enabled(enabled)