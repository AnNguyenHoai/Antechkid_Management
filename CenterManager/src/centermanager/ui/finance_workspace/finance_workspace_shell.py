# -*- coding: utf-8 -*-
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
    QPushButton,
)

from centermanager.core.clock import get_clock
from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.finance_workspace.action_state import has_capability
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage
from centermanager.ui.finance_workspace.income_list_page import IncomeListPage
from centermanager.ui.finance_workspace.expense_list_page import ExpenseListPage
from centermanager.ui.finance_workspace.outstanding_list_page import OutstandingListPage
from centermanager.ui.finance_workspace.financial_settlement_page import FinancialSettlementPage
from centermanager.ui.finance_workspace.finance_period_config_dialog import FinancePeriodConfigDialog


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

        shared_bus = (
            event_bus
            or getattr(collaboration_manager, "_event_bus", None)
            or getattr(income_service, "_event_bus", None)
            or getattr(expense_service, "_event_bus", None)
            or EventBus()
        )
        self._event_bus = shared_bus
        self._authorized = False
        self._write_enabled = False
        self._period_selector_ready = False

        self._finance_period_service = finance_period_service or getattr(
            self._dashboard_service, "_finance_period_service", None
        )
        if self._finance_period_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                from centermanager.services.finance_period_service import FinancePeriodService

                self._finance_period_service = FinancePeriodService(session_factory)

        if self._settlement_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                from centermanager.services.financial_settlement_service import FinancialSettlementService

                self._settlement_service = FinancialSettlementService(session_factory)

        self._income_service._event_bus = self._event_bus
        if hasattr(self._expense_service, "set_event_bus"):
            self._expense_service.set_event_bus(self._event_bus)

        self._setup_ui()
        self._connect_signals()
        self._event_bus.register(FinanceDataChanged, self._on_finance_data_changed)

        self._authorized = self._has_finance_access()
        if self._authorized:
            self._populate_period_selector()
            self._period_selector_ready = True
            self.navigate_to("dashboard")
        else:
            self._period_selector_ready = True
            self.nav.setEnabled(False)
            self.header.set_context("Finance Workspace", "Access restricted")

    def _has_finance_access(self) -> bool:
        try:
            user = get_current_user()
            return bool(user and (user.has_permission("finance.view") or user.is_admin))
        except Exception:
            return False

    def _can_manage_periods(self) -> bool:
        try:
            user = get_current_user()
            return bool(
                user
                and (user.has_permission("finance.period.manage") or user.is_admin)
            )
        except Exception:
            return False

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.header = WorkspaceHeader("Finance Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        period_bar = QWidget()
        period_layout = QHBoxLayout(period_bar)
        period_layout.setContentsMargins(16, 8, 16, 8)
        period_layout.setSpacing(8)
        period_layout.addWidget(QLabel("Finance period:"))

        self.period_combo = QComboBox()
        self.period_combo.setMinimumWidth(280)
        self.period_combo.setToolTip(
            "Canonical FinancePeriod. Exact bounds are the accounting identity."
        )
        period_layout.addWidget(self.period_combo)

        self.period_label = QLabel("")
        period_layout.addWidget(self.period_label)
        period_layout.addStretch()
        self.period_config_btn = QPushButton("⚙ Cấu hình kỳ")
        self.period_config_btn.setToolTip(
            "Quản lý cấu hình Finance Period theo ngày hiệu lực"
        )
        self.period_config_btn.setVisible(self._can_manage_periods())
        self.period_config_btn.setEnabled(False)
        self.period_config_btn.clicked.connect(self._open_period_config)
        period_layout.addWidget(self.period_config_btn)
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
        self.period_combo.currentIndexChanged.connect(self._on_period_selection_changed)
        self.settlement_page.settlement_changed.connect(self._refresh_all_period_pages)

    @staticmethod
    def _period_display_label(period, business_date: date) -> str:
        bounds = f"{period.period_start:%d/%m/%Y} – {period.period_end:%d/%m/%Y}"
        if period.contains(business_date):
            return f"Current · {bounds}"
        return bounds

    def _populate_period_selector(self, preserve_start: Optional[date] = None) -> None:
        previous = self.period_combo.blockSignals(True)
        try:
            if preserve_start is None:
                selected = self.period_combo.currentData()
                preserve_start = getattr(selected, "period_start", None)

            self.period_combo.clear()
            if self._finance_period_service is None:
                self.period_label.setText("Finance period service unavailable")
                return

            business_date = get_clock().today()
            periods = self._finance_period_service.list_resolved_periods(business_date)
            selected_index = -1
            current_index = -1
            for index, period in enumerate(periods):
                self.period_combo.addItem(
                    self._period_display_label(period, business_date),
                    period,
                )
                if period.period_start == preserve_start:
                    selected_index = index
                if period.contains(business_date):
                    current_index = index

            if selected_index < 0:
                selected_index = current_index
            if selected_index < 0 and self.period_combo.count() > 0:
                selected_index = 0
            if selected_index >= 0:
                self.period_combo.setCurrentIndex(selected_index)
            else:
                self.period_label.setText("Finance period not configured")
        except Exception as exc:
            self.period_combo.clear()
            self.period_label.setText(f"Unable to enumerate Finance periods: {exc}")
        finally:
            self.period_combo.blockSignals(previous)

    def _selected_period(self):
        return self.period_combo.currentData()

    @staticmethod
    def _target_date_for_period(period, business_date: date) -> date:
        if period is None:
            return business_date
        if period.contains(business_date):
            return business_date
        return period.period_start

    def _resolve_shared_period(self):
        """Return target date, exact canonical bounds, configured and closed state."""
        business_date = get_clock().today()
        period = self._selected_period()
        if period is None:
            self.period_label.setText("Finance period not configured")
            return business_date, None, None, False, False

        target_date = self._target_date_for_period(period, business_date)
        self.period_label.setText(
            f"{period.period_start:%d/%m/%Y} – {period.period_end:%d/%m/%Y}"
        )
        closed = False
        if self._finance_period_service is not None:
            try:
                closed = self._finance_period_service.is_period_closed(target_date)
            except Exception:
                closed = False
        return target_date, period.period_start, period.period_end, True, closed

    def _period_context(self) -> dict:
        target_date, period_start, period_end, configured, closed = self._resolve_shared_period()
        return {
            "target_date": target_date,
            "period_start": period_start,
            "period_end": period_end,
            "period_configured": configured,
            "period_closed": closed,
        }

    def _refresh_pages(self, pages) -> None:
        context = self._period_context()
        for page in pages:
            page.refresh(**context)

    def _refresh_all_period_pages(self) -> None:
        if not self._has_finance_access():
            return
        self._refresh_pages([
            self.dashboard_page,
            self.income_page,
            self.expense_page,
            self.outstanding_page,
            self.settlement_page,
        ])

    def _refresh_page(self, page) -> None:
        self._refresh_pages([page])

    def _open_period_config(self) -> None:
        if self._finance_period_service is None or not self._can_manage_periods():
            return
        if (
            self._collaboration_manager is not None
            and not self._collaboration_manager.ensure_write()
        ):
            if (
                self._notification_service is not None
                and hasattr(self._notification_service, "notify")
            ):
                self._notification_service.notify(
                    "You must be in WRITE mode to manage Finance Period.",
                    "warning",
                )
            return

        selected = self._selected_period()
        preserve_start = getattr(selected, "period_start", None)
        FinancePeriodConfigDialog(
            self._finance_period_service,
            self._collaboration_manager,
            self._notification_service,
            parent=self,
        ).exec()
        self._populate_period_selector(preserve_start=preserve_start)
        self._refresh_all_period_pages()

    def _on_period_selection_changed(self, _index: int) -> None:
        if not self._period_selector_ready or not self._has_finance_access():
            return
        self._refresh_all_period_pages()

    def _on_finance_data_changed(self, _event: FinanceDataChanged) -> None:
        self._refresh_all_period_pages()

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
        if page_id == "settlement" and not has_capability(Capability.FINANCE_SETTLEMENT_VIEW):
            if self._notification_service is not None and hasattr(self._notification_service, "notify"):
                self._notification_service.notify(
                    "Settlement access requires finance.settlement.view.",
                    "warning",
                )
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
        selected = self._selected_period()
        preserve_start = getattr(selected, "period_start", None)
        self._populate_period_selector(preserve_start=preserve_start)
        current = self.content_stack.currentWidget()
        if current is not None:
            self._refresh_page(current)

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.income_page.set_write_enabled(enabled)
        self.expense_page.set_write_enabled(enabled)
        self.settlement_page.set_write_enabled(enabled)
        self.period_config_btn.setEnabled(
            self._write_enabled and self._can_manage_periods()
        )
