# -*- coding: utf-8 -*-
"""Student finance summary migrated to Design System V2.

Finance remains the owner of money. This Student workspace surface only consumes
canonical Finance read APIs and projects permission/empty/error states.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from centermanager.dto.outstanding_dto import StudentOutstandingSummary
from centermanager.models.income import Income
from centermanager.services.class_service import ClassService
from centermanager.services.finance_period_service import FinancePeriodService
from centermanager.services.income_service import IncomeService
from centermanager.services.outstanding_service import OutstandingService
from centermanager.services.permission_service import PermissionService
from centermanager.services.student_service import StudentService
from centermanager.ui.design_system.feedback import FeedbackController
from centermanager.ui.design_system.foundation import Button, ButtonVariant, Card
from centermanager.ui.design_system.state_patterns import PermissionState
from centermanager.ui.design_system.tokens import COLORS, FONT_WEIGHTS, SPACING, TYPOGRAPHY
from centermanager.ui.shared import DataTable, TableDensity

logger = logging.getLogger(__name__)


class StudentFinancialWidget(QWidget):
    financial_updated = Signal()
    open_finance_clicked = Signal()

    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        permission_service: PermissionService,
        outstanding_service: OutstandingService,
        parent: Optional[QWidget] = None,
        finance_period_service: Optional[FinancePeriodService] = None,
        feedback_controller: Optional[FeedbackController] = None,
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._permission_service = permission_service
        self._outstanding_service = outstanding_service
        self._feedback = feedback_controller or FeedbackController(self)
        self._student_id: Optional[int] = None
        self._incomes: List[Income] = []
        self._summary: Optional[StudentOutstandingSummary] = None
        self._requested_period_start: Optional[date] = None
        self._requested_on_date: Optional[date] = None
        self._resolved_period_start: Optional[date] = None
        self._resolved_period_end: Optional[date] = None
        self._income_load_failed = False
        self._summary_load_failed = False

        self._finance_period_service = finance_period_service
        if self._finance_period_service is None:
            session_factory = getattr(self._income_service, "_session_factory", None)
            if session_factory is not None:
                self._finance_period_service = FinancePeriodService(session_factory)

        self._setup_ui()
        self._show_empty()

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        self._feedback = controller

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.state_stack = QStackedWidget(self)
        self.permission_state = PermissionState(
            title="Finance access required",
            description="Your current role does not allow Student finance information. Finance data remains protected by the Finance permission model.",
            parent=self.state_stack,
        )
        self.state_stack.addWidget(self.permission_state)

        self.content = QWidget(self.state_stack)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["lg"])

        header = Card(
            "Finance summary",
            "Read-only tuition and payment context for this student.",
            parent=self.content,
        )
        self.period_label = QLabel("Finance period: —", header)
        self.period_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['body_small']}px;"
        )
        header.add_widget(self.period_label)
        self.open_finance_btn = Button(
            "Open Finance Workspace",
            variant=ButtonVariant.PRIMARY,
            parent=header,
        )
        self.open_finance_btn.clicked.connect(self.open_finance_clicked.emit)
        header.add_widget(self.open_finance_btn)
        layout.addWidget(header)

        summary_wrap = QWidget(self.content)
        summary_layout = QHBoxLayout(summary_wrap)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(SPACING["md"])
        self.total_expected_label = self._create_summary_card("Expected tuition", "0 VND")
        self.total_paid_label = self._create_summary_card("Paid", "0 VND")
        self.outstanding_label = self._create_summary_card("Outstanding", "0 VND")
        self.status_label = self._create_summary_card("Status", "No data")
        for card in (
            self.total_expected_label,
            self.total_paid_label,
            self.outstanding_label,
            self.status_label,
        ):
            summary_layout.addWidget(card)
        layout.addWidget(summary_wrap)

        class_card = Card(
            "Tuition by class",
            "Expected tuition, payments and outstanding balance for each enrolled class.",
            parent=self.content,
        )
        self.detail_data_table = DataTable(
            [
                {"key": "class", "label": "Class", "sortable": True},
                {"key": "expected", "label": "Expected", "sortable": True},
                {"key": "paid", "label": "Paid", "sortable": True},
                {"key": "outstanding", "label": "Outstanding", "sortable": True},
                {"key": "status", "label": "Status", "sortable": True},
            ],
            page_size=20,
            density=TableDensity.COMPACT,
            empty_title="No class tuition data",
            empty_message="Tuition details will appear when the student has a configured enrollment.",
            parent=class_card,
        )
        class_card.add_widget(self.detail_data_table)
        layout.addWidget(class_card)

        history_card = Card(
            "Payment history",
            "Payments recorded by Finance for the selected finance period.",
            parent=self.content,
        )
        self.payment_table = DataTable(
            [
                {"key": "date", "label": "Date", "sortable": True},
                {"key": "class", "label": "Class", "sortable": True},
                {"key": "type", "label": "Type", "sortable": True},
                {"key": "amount", "label": "Amount", "sortable": True},
                {"key": "method", "label": "Method", "sortable": True},
                {"key": "received_by", "label": "Received by", "sortable": True},
            ],
            page_size=20,
            density=TableDensity.COMPACT,
            empty_title="No payment records",
            empty_message="Payments for this finance period will appear here.",
            parent=history_card,
        )
        history_card.add_widget(self.payment_table)
        layout.addWidget(history_card, 1)

        self.state_stack.addWidget(self.content)
        root.addWidget(self.state_stack)
        self.state_stack.setCurrentWidget(self.content)

        # Compatibility aliases retained for older tests/callers.
        self.detail_table = self.detail_data_table.table
        self.table = self.payment_table.table

    def _create_summary_card(self, label: str, value: str) -> Card:
        card = Card(parent=self.content)
        label_widget = QLabel(label, card)
        label_widget.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;"
        )
        value_widget = QLabel(value, card)
        value_widget.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['section_title']}px; "
            f"font-weight: {FONT_WEIGHTS['semibold']};"
        )
        card.add_widget(label_widget)
        card.add_widget(value_widget)
        card._value_widget = value_widget
        return card

    def _show_empty(self) -> None:
        self.detail_data_table.set_data([], 0)
        self.payment_table.set_data([], 0)
        self.total_expected_label._value_widget.setText("—")
        self.total_paid_label._value_widget.setText("—")
        self.outstanding_label._value_widget.setText("—")
        self.status_label._value_widget.setText("No data")

    def _show_data(self) -> None:
        self.state_stack.setCurrentWidget(self.content)

    def set_finance_period(
        self,
        period_start: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> None:
        self._requested_period_start = period_start
        self._requested_on_date = on_date
        if self._student_id is not None:
            self.set_student(self._student_id)

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        if not self._can_view_finance():
            self._incomes = []
            self._summary = None
            self._resolved_period_start = None
            self._resolved_period_end = None
            self._update_period_label()
            self._show_empty()
            self.state_stack.setCurrentWidget(self.permission_state)
            return

        self.state_stack.setCurrentWidget(self.content)
        self.detail_data_table.set_loading(True)
        self.payment_table.set_loading(True)
        self._income_load_failed = False
        self._summary_load_failed = False
        target_date, period_start, period_end = self._resolve_finance_period_context()
        self._resolved_period_start = period_start
        self._resolved_period_end = period_end
        self._update_period_label()
        self._load_outstanding_summary(period_start, target_date)
        self._load_incomes(period_start, period_end)
        self._update_ui()

    def _can_view_finance(self) -> bool:
        try:
            allowed = bool(self._permission_service.has_permission("finance.view"))
            self.open_finance_btn.setVisible(allowed)
            return allowed
        except Exception as exc:
            logger.exception("Failed to evaluate finance data permission")
            self.open_finance_btn.setVisible(False)
            self._feedback.system_error(
                exc,
                message="Finance access could not be verified.",
                key="student-finance-permission",
            )
            return False

    def _resolve_finance_period_context(self) -> Tuple[date, Optional[date], Optional[date]]:
        target_date = self._requested_on_date or self._requested_period_start or date.today()
        if self._finance_period_service is None:
            return target_date, self._requested_period_start, None
        try:
            lookup_date = self._requested_period_start or target_date
            config = self._finance_period_service.get_active_period(lookup_date)
            if config is None:
                return target_date, None, None
            period_start, period_end = self._finance_period_service.get_period_bounds(
                config.effective_from,
                lookup_date,
                config.duration_months,
            )
            return target_date, period_start, period_end
        except Exception as exc:
            logger.exception("Failed to resolve Finance period for student financial view")
            self._feedback.system_error(
                exc,
                message="The Finance period could not be resolved.",
                key="student-finance-period",
            )
            return target_date, self._requested_period_start, None

    def _update_period_label(self) -> None:
        if self._resolved_period_start is None:
            self.period_label.setText("Finance period: Not configured")
            return
        if self._resolved_period_end is None:
            self.period_label.setText(f"Finance period: from {self._resolved_period_start:%d/%m/%Y}")
            return
        self.period_label.setText(
            f"Finance period: {self._resolved_period_start:%d/%m/%Y} - {self._resolved_period_end:%d/%m/%Y}"
        )

    def _load_incomes(self, period_start: Optional[date], period_end: Optional[date]) -> None:
        if self._student_id is None or not self._can_view_finance() or period_start is None:
            self._incomes = []
            return
        try:
            first_page, total = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=1,
                finance_period_start=period_start,
                date_from=period_start,
                date_to=period_end,
                status=Income.STATUS_ACTIVE,
                sort_by="payment_date",
                ascending=False,
            )
            if total <= 1:
                self._incomes = first_page
                return
            items, _ = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=total,
                finance_period_start=period_start,
                date_from=period_start,
                date_to=period_end,
                status=Income.STATUS_ACTIVE,
                sort_by="payment_date",
                ascending=False,
            )
            self._incomes = items
        except Exception as exc:
            logger.exception("Failed to load incomes for student")
            self._income_load_failed = True
            self._incomes = []
            self._feedback.system_error(
                exc,
                message="Student payment history could not be loaded.",
                key="student-finance-payments",
            )

    def _load_outstanding_summary(self, period_start: Optional[date], target_date: date) -> None:
        if self._student_id is None or not self._can_view_finance():
            self._summary = None
            return
        try:
            self._summary = self._outstanding_service.get_student_summary(
                self._student_id,
                period_start=period_start,
                on_date=target_date,
            )
        except Exception as exc:
            logger.exception("Failed to load outstanding summary")
            self._summary_load_failed = True
            self._summary = None
            self._feedback.system_error(
                exc,
                message="Student tuition summary could not be loaded.",
                key="student-finance-summary",
            )

    def _update_ui(self) -> None:
        self._show_data()
        if self._summary_load_failed:
            self.detail_data_table.set_error(
                "Tuition details could not be loaded.",
                title="Unable to load tuition",
                retry_callback=self.refresh,
            )
        else:
            self._update_summary()
            self._update_detail_table()

        if self._income_load_failed:
            self.payment_table.set_error(
                "Payment history could not be loaded.",
                title="Unable to load payments",
                retry_callback=self.refresh,
            )
        else:
            self._update_payment_history()

    def _update_summary(self) -> None:
        if self._summary is None:
            self.total_expected_label._value_widget.setText("—")
            self.total_paid_label._value_widget.setText("—")
            self.outstanding_label._value_widget.setText("—")
            self.status_label._value_widget.setText("No tuition data")
            return

        self.total_paid_label._value_widget.setText(f"{self._summary.total_paid:,.0f} VND")
        has_unconfigured = bool(self._summary.has_unconfigured_tuition)
        if has_unconfigured and self._summary.total_expected == 0:
            self.total_expected_label._value_widget.setText("Not configured")
            self.outstanding_label._value_widget.setText("Unknown")
            self.status_label._value_widget.setText("Tuition not configured")
            return

        self.total_expected_label._value_widget.setText(f"{self._summary.total_expected:,.0f} VND")
        outstanding = self._summary.total_outstanding
        self.outstanding_label._value_widget.setText(f"{outstanding:,.0f} VND")
        if has_unconfigured:
            status_text = "Partially configured"
        elif outstanding > 0:
            status_text = "Outstanding"
        elif outstanding == 0:
            status_text = "Paid"
        else:
            status_text = "Overpaid"
        self.status_label._value_widget.setText(status_text)

    def _update_detail_table(self) -> None:
        rows = []
        if self._summary and self._summary.details:
            for detail in self._summary.details:
                rows.append(
                    {
                        "class": detail.class_name,
                        "expected": f"{detail.expected_tuition:,.0f} VND" if detail.tuition_configured else "Not configured",
                        "paid": f"{detail.paid:,.0f} VND",
                        "outstanding": f"{detail.outstanding:,.0f} VND" if detail.tuition_configured else "Unknown",
                        "status": detail.status if detail.tuition_configured else "Not configured",
                    }
                )
        self.detail_data_table.set_data(rows, len(rows))

    def _update_payment_history(self) -> None:
        rows = []
        for income in self._incomes:
            rows.append(
                {
                    "date": income.payment_date.strftime("%d/%m/%Y"),
                    "class": income.class_.name if income.class_ else "—",
                    "type": income.income_type,
                    "amount": f"{income.amount:,.0f} VND",
                    "method": income.payment_method,
                    "received_by": income.received_by or "—",
                }
            )
        self.payment_table.set_data(rows, len(rows))

    def refresh(self) -> None:
        if self._student_id is not None:
            self.set_student(self._student_id)

    def set_write_enabled(self, _enabled: bool) -> None:
        """Finance is read-only from the Student workspace."""
        return
