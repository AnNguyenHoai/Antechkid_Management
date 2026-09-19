# src/centermanager/ui/student_workspace/financial_widget.py
# -*- coding: utf-8 -*-
"""
FinancialWidget - read-only student financial summary and payment history.
All Income writes belong to Finance Workspace.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
)

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.models.income import Income
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY

logger = logging.getLogger(__name__)


class FinancialWidget(QWidget):
    """Read-only Financial tab for student detail."""

    # Retained for compatibility with existing workspace wiring. The read-only
    # widget no longer emits finance mutations itself.
    data_changed = Signal()

    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        permission_service: PermissionService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._permission_service = permission_service
        self._student_id: Optional[int] = None
        self._student = None
        self._incomes: List[Income] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['lg'])

        # Summary is intentionally read-only. Finance Workspace is the single
        # write surface for tuition collection and all other Income records.
        self.summary_layout = QHBoxLayout()
        self.summary_layout.setSpacing(SPACING['md'])
        self.total_paid_label = QLabel("Total Paid: 0")
        self.total_paid_label.setStyleSheet(
            f"font-size: {TYPOGRAPHY['section_title']}px; font-weight: bold; color: {COLORS['success']};"
        )
        self.summary_layout.addWidget(self.total_paid_label)
        self.summary_layout.addStretch()

        finance_hint = QLabel("Thu học phí được quản lý tại Finance → Income")
        finance_hint.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.summary_layout.addWidget(finance_hint)
        layout.addLayout(self.summary_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        history_label = QLabel("Payment History")
        history_label.setStyleSheet(
            f"font-size: {TYPOGRAPHY['section_title']}px; font-weight: 600;"
        )
        layout.addWidget(history_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Date", "Class", "Type", "Amount", "Method", "Received By"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        self.empty_label = QLabel("No payment history yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; padding: 20px;"
        )
        layout.addWidget(self.empty_label)

    def set_student(self, student_id: int) -> None:
        """Load financial data only for users authorized to view Finance."""
        self._student_id = student_id
        if not self._can_view_finance():
            self._incomes = []
            self._clear()
            return
        try:
            self._student = self._student_service.get_student(student_id)
        except Exception:
            logger.exception("Failed to load student")
            self._student = None
            self._clear()
            return

        self._load_incomes()
        self._update_ui()

    def _can_view_finance(self) -> bool:
        try:
            return bool(self._permission_service.has_permission("finance.view"))
        except Exception:
            logger.exception("Failed to evaluate finance data permission")
            return False

    def _load_incomes(self) -> None:
        """Load income records for the current student."""
        if self._student_id is None or not self._can_view_finance():
            self._incomes = []
            return
        try:
            items, _ = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=1000,
            )
            self._incomes = items
        except Exception:
            logger.exception("Failed to load incomes for student")
            self._incomes = []

    def _update_ui(self) -> None:
        self._update_summary()
        self._update_table()

    def _update_summary(self) -> None:
        total_paid = sum(i.amount for i in self._incomes)
        self.total_paid_label.setText(f"Total Paid: {total_paid:,.0f} VND")

    def _update_table(self) -> None:
        self.table.setRowCount(len(self._incomes))
        self.empty_label.setVisible(len(self._incomes) == 0)
        self.table.setVisible(len(self._incomes) > 0)

        for row, income in enumerate(self._incomes):
            self.table.setItem(row, 0, QTableWidgetItem(income.payment_date.strftime("%d/%m/%Y")))
            class_name = income.class_.name if income.class_ else "-"
            self.table.setItem(row, 1, QTableWidgetItem(class_name))
            self.table.setItem(row, 2, QTableWidgetItem(income.income_type))
            self.table.setItem(row, 3, QTableWidgetItem(f"{income.amount:,.0f}"))
            self.table.setItem(row, 4, QTableWidgetItem(income.payment_method))
            self.table.setItem(row, 5, QTableWidgetItem(income.received_by or "-"))

    def _clear(self) -> None:
        self.table.setRowCount(0)
        self.total_paid_label.setText("Total Paid: 0")
        self.empty_label.setVisible(True)
        self.table.setVisible(False)

    def refresh(self) -> None:
        """External refresh."""
        if self._student_id is not None:
            self.set_student(self._student_id)
