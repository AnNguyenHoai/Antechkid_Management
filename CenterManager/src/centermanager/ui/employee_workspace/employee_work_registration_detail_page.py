from __future__ import annotations

from datetime import timedelta

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.ui.employee_workspace.table_layout import (
    CENTER,
    LEFT,
    RIGHT,
    EmployeeTableColumn,
    configure_employee_table,
    set_employee_row,
)


DETAIL_COLUMNS = [
    EmployeeTableColumn("fixed", 118, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 78, RIGHT),
    EmployeeTableColumn("fixed", 118, CENTER),
    EmployeeTableColumn("stretch", None, LEFT),
]


class EmployeeWorkRegistrationDetailPage(QWidget):
    """Manager detail view for one employee's weekly work registration."""

    def __init__(self, registration_service, registration, parent=None):
        super().__init__(parent)
        self._rs = registration_service
        self.registration = registration
        self._write_enabled = False
        self._period_status = EmployeeWorkRegistrationPeriod.STATUS_OPEN
        self._admin_override = False
        self._setup()
        self.refresh()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        self.title = QLabel("Registration Detail")
        self.title.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(self.title)

        self.summary = QLabel("-")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.status = QLabel("Status: -")
        self.status.setStyleSheet("font-size:15px;font-weight:600;")
        root.addWidget(self.status)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Date", "From", "To", "Hours", "Work Type", "Notes"]
        )
        configure_employee_table(
            self.table,
            DETAIL_COLUMNS,
            row_height=36,
            minimum_height=300,
        )
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.accept_btn = QPushButton("Accept")
        self.reopen_btn = QPushButton("Reopen")
        self.edit_btn = QPushButton("Edit Selected")
        self.delete_btn = QPushButton("Delete Selected")
        actions.addWidget(self.back_btn)
        actions.addStretch()
        actions.addWidget(self.accept_btn)
        actions.addWidget(self.reopen_btn)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        root.addLayout(actions)

        self.back_btn.clicked.connect(self._back)
        self.accept_btn.clicked.connect(self._accept)
        self.reopen_btn.clicked.connect(self._reopen)
        self.edit_btn.clicked.connect(self._edit_selected)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.table.itemSelectionChanged.connect(self._update_actions)

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._update_actions()

    def refresh(self) -> None:
        can_override = getattr(self._rs, "can_admin_override", None)
        self._admin_override = bool(can_override()) if can_override is not None else False
        registration = self.registration
        employee = getattr(registration, "employee", None)
        name = getattr(employee, "full_name", None) or "-"
        code = getattr(employee, "employee_code", None) or "-"
        period = getattr(registration, "period", None)
        if period and getattr(period, "week_start", None):
            week_start = period.week_start
            week_end = getattr(period, "week_end", week_start + timedelta(days=6))
            period_text = f"{week_start:%d/%m/%Y} - {week_end:%d/%m/%Y}"
            self._period_status = getattr(
                period,
                "status",
                EmployeeWorkRegistrationPeriod.STATUS_OPEN,
            )
        else:
            period_text = "-"

        self.title.setText(f"{name} • Registration Detail")
        self.summary.setText(
            f"Employee: {name} ({code})\n"
            f"Registration week: {period_text}\n"
            f"Availability blocks: {len(registration.blocks)}"
        )
        effective = (
            "ADMIN OVERRIDE"
            if self._admin_override
            and self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
            else self._period_status
        )
        self.status.setText(
            f"Status: {registration.status} • Period: {self._period_status} • Access: {effective}"
        )

        self.table.setRowCount(0)
        total_minutes = 0
        for block in sorted(registration.blocks, key=lambda b: (b.work_date, b.start_time)):
            minutes = (
                block.end_time.hour * 60
                + block.end_time.minute
                - block.start_time.hour * 60
                - block.start_time.minute
            )
            total_minutes += minutes
            row = self.table.rowCount()
            self.table.insertRow(row)
            set_employee_row(
                self.table,
                row,
                [
                    block.work_date.strftime("%d/%m/%Y"),
                    block.start_time.strftime("%H:%M"),
                    block.end_time.strftime("%H:%M"),
                    f"{minutes / 60:.2f}",
                    block.work_type,
                    block.notes or "",
                ],
                DETAIL_COLUMNS,
                row_user_data=block.id,
            )

        self.table.setToolTip(f"Total availability: {total_minutes / 60:.2f} hours")
        self._update_actions()

    def _update_actions(self) -> None:
        registration = self.registration
        period_open = self._period_status != EmployeeWorkRegistrationPeriod.STATUS_CLOSED
        can_override = self._admin_override
        self.accept_btn.setEnabled(
            self._write_enabled
            and period_open
            and registration.status == EmployeeWorkRegistration.STATUS_SUBMITTED
        )
        self.reopen_btn.setEnabled(
            self._write_enabled
            and registration.status == EmployeeWorkRegistration.STATUS_ACCEPTED
            and (period_open or can_override)
        )
        blocks = sorted(registration.blocks, key=lambda b: (b.work_date, b.start_time))
        has_selection = 0 <= self.table.currentRow() < len(blocks)
        can_edit = (
            self._write_enabled
            and has_selection
            and (period_open or can_override)
            and (
                registration.status == EmployeeWorkRegistration.STATUS_DRAFT
                or can_override
            )
        )
        self.edit_btn.setEnabled(can_edit)
        self.delete_btn.setEnabled(can_edit)

    def _week_start(self):
        period = getattr(self.registration, "period", None)
        week_start = getattr(period, "week_start", None)
        if week_start is None:
            raise ValueError("Registration week is unavailable.")
        return week_start

    def _reload(self):
        week_start = self._week_start()
        self.registration = self._rs.list_for_employee(
            self.registration.employee_id,
            week_start,
        )
        self.refresh()

    def _accept(self):
        if not self._write_enabled:
            return
        try:
            self._rs.accept(self.registration.employee_id, self._week_start())
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Accept Registration", str(exc))

    def _reopen(self):
        if not self._write_enabled:
            return
        try:
            self._rs.reopen(self.registration.employee_id, self._week_start())
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Reopen Registration", str(exc))

    def _selected_block(self):
        row = self.table.currentRow()
        blocks = sorted(self.registration.blocks, key=lambda b: (b.work_date, b.start_time))
        if row < 0 or row >= len(blocks):
            return None
        return blocks[row]

    @staticmethod
    def _ask_reason(parent, title, prompt):
        reason, accepted = QInputDialog.getText(parent, title, prompt)
        value = reason.strip() if accepted else ""
        return value if accepted and value else None

    def _edit_selected(self):
        block = self._selected_block()
        if block is None or not self.edit_btn.isEnabled():
            return
        from centermanager.ui.employee_workspace.employee_work_registration_widget import WorkRegistrationDialog

        period = self.registration.period
        min_date = period.week_start
        max_date = period.week_start + timedelta(days=6)
        dialog = WorkRegistrationDialog(
            self,
            block,
            min_date=min_date,
            max_date=max_date,
        )
        if not dialog.exec():
            return
        work_date, start_time, end_time, work_type, notes = dialog.values()
        try:
            self._rs.update(
                block.id,
                work_date=work_date,
                start_time=start_time,
                end_time=end_time,
                work_type=work_type,
                notes=notes,
            )
            self._reload()
        except Exception as exc:
            QMessageBox.warning(self, "Edit Registration", str(exc))

    def _delete_selected(self):
        block = self._selected_block()
        if block is None or not self.delete_btn.isEnabled():
            return
        reason = self._ask_reason(
            self,
            "Delete Availability",
            "Reason for deleting this availability block:",
        )
        if not reason:
            return
        if QMessageBox.question(
            self,
            "Confirm Availability Deletion",
            "Delete the selected availability block?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._rs.delete(block.id)
            refreshed = self._rs.list_for_employee(
                self.registration.employee_id,
                self._week_start(),
            )
            if refreshed is not None:
                self.registration = refreshed
                self.refresh()
            else:
                self._back()
        except Exception as exc:
            QMessageBox.warning(self, "Delete Availability", str(exc))

    def _back(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "close_registration_detail"):
            parent.close_registration_detail()
