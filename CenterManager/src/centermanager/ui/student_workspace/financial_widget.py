# src/centermanager/ui/student_workspace/financial_widget.py
# -*- coding: utf-8 -*-
"""
FinancialWidget - displays student financial summary and payment history.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QMessageBox
)

from centermanager.services.income_service import IncomeService
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.services.permission_service import PermissionService
from centermanager.models.income import Income
from centermanager.ui.student_workspace.collect_tuition_dialog import CollectTuitionDialog
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY

logger = logging.getLogger(__name__)


class FinancialWidget(QWidget):
    """Financial tab for student detail."""
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
        self._update_permission()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['lg'])

        # Summary cards
        self.summary_layout = QHBoxLayout()
        self.summary_layout.setSpacing(SPACING['md'])
        self.total_paid_label = QLabel("Total Paid: 0")
        self.total_paid_label.setStyleSheet(f"font-size: {TYPOGRAPHY['section_title']}px; font-weight: bold; color: {COLORS['success']};")
        self.summary_layout.addWidget(self.total_paid_label)

        self.summary_layout.addStretch()

        self.collect_btn = QPushButton("💰 Collect Tuition")
        self.collect_btn.setStyleSheet("""
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1565c0;
            }
            QPushButton:disabled {
                background: #b0b0b0;
            }
        """)
        self.collect_btn.clicked.connect(self._on_collect)
        self.summary_layout.addWidget(self.collect_btn)

        layout.addLayout(self.summary_layout)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Payment history table
        history_label = QLabel("Payment History")
        history_label.setStyleSheet(f"font-size: {TYPOGRAPHY['section_title']}px; font-weight: 600;")
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

        # Empty state
        self.empty_label = QLabel("No payment history yet.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 20px;")
        layout.addWidget(self.empty_label)

    def _update_permission(self) -> None:
        """Enable/disable collect button based on permission."""
        has_perm = self._permission_service.has_permission("finance.income.create")
        self.collect_btn.setEnabled(has_perm)
        if not has_perm:
            self.collect_btn.setToolTip("You don't have permission to collect tuition.")

    def set_student(self, student_id: int) -> None:
        """Load financial data for a student."""
        self._student_id = student_id
        try:
            self._student = self._student_service.get_student(student_id)
        except Exception as e:
            logger.exception("Failed to load student")
            self._student = None
            self._clear()
            return

        self._load_incomes()
        self._update_ui()

    def _load_incomes(self) -> None:
        """Load income records for the current student."""
        if self._student_id is None:
            self._incomes = []
            return
        try:
            items, _ = self._income_service.list_incomes(
                student_id=self._student_id,
                page=1,
                per_page=1000
            )
            self._incomes = items
        except Exception as e:
            logger.exception("Failed to load incomes for student")
            self._incomes = []

    def _update_ui(self) -> None:
        """Refresh summary and table."""
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

    def _on_collect(self) -> None:
        if self._student_id is None:
            return
        dialog = CollectTuitionDialog(
            self._income_service,
            self._student_service,
            self._class_service,
            self._permission_service,
            self._student_id,
            parent=self
        )
        if dialog.exec() == CollectTuitionDialog.DialogCode.Accepted:
            self._load_incomes()
            self._update_ui()
            self.data_changed.emit()

    def refresh(self) -> None:
        """External refresh."""
        if self._student_id is not None:
            self.set_student(self._student_id)