from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QPushButton, QComboBox, QDateEdit, QTimeEdit, QFormLayout, QLineEdit,
    QMessageBox, QLabel, QDialog, QDialogButtonBox,
)

from centermanager.models.employee_working_time import EmployeeWorkingTimeEntry
from centermanager.ui.employee_workspace.error_boundary import execute_ui_operation
from centermanager.ui.employee_workspace.table_layout import (
    CENTER,
    LEFT,
    RIGHT,
    EmployeeTableColumn,
    configure_employee_table,
    set_employee_row,
)

logger = logging.getLogger(__name__)


WORKING_TIME_COLUMNS = [
    EmployeeTableColumn("fixed", 118, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 78, RIGHT),
    EmployeeTableColumn("fixed", 112, CENTER),
    EmployeeTableColumn("fixed", 110, CENTER),
    EmployeeTableColumn("stretch", None, CENTER),
]


class WorkingTimeBookingDialog(QDialog):
    def __init__(self, parent=None, entry=None, default_date=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Working Time")
        self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd/MM/yyyy")
        d = default_date or date.today()
        self.day.setDate(QDate(d.year, d.month, d.day))
        self.start = QTimeEdit()
        self.start.setDisplayFormat("HH:mm")
        self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit()
        self.end.setDisplayFormat("HH:mm")
        self.end.setTime(QTime(17, 0))
        self.typ = QComboBox()
        self.typ.addItems(["WORK", "TEACHING", "MEETING", "TRAINING", "ADMIN", "OTHER"])
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional")
        form.addRow("Date", self.day)
        form.addRow("Start", self.start)
        form.addRow("End", self.end)
        form.addRow("Work type", self.typ)
        form.addRow("Notes", self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if entry:
            self.day.setDate(QDate(entry.work_date.year, entry.work_date.month, entry.work_date.day))
            self.start.setTime(QTime(entry.start_time.hour, entry.start_time.minute))
            if entry.end_time:
                self.end.setTime(QTime(entry.end_time.hour, entry.end_time.minute))
            self.typ.setCurrentText(entry.work_type)
            self.notes.setText(entry.notes or "")

    def values(self):
        return (
            self.day.date().toPython(),
            self.start.time().toPython(),
            self.end.time().toPython(),
            self.typ.currentText(),
            self.notes.text().strip() or None,
        )


class EmployeeWorkingTimeWidget(QWidget):
    """Working-time booking, check-in/out and monthly summary."""

    def __init__(self, service, employee, editable=False, management=False, parent=None):
        super().__init__(parent)
        self.service = service
        self.employee = employee
        self.editable = bool(editable)
        self.management = bool(management)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        self.month = QDateEdit()
        self.month.setCalendarPopup(True)
        self.month.setDisplayFormat("MM/yyyy")
        self.month.setDate(QDate.currentDate())
        self.month.dateChanged.connect(self.refresh)
        controls.addWidget(QLabel("Month"))
        controls.addWidget(self.month)

        self.summary = QLabel("-")
        self.summary.setWordWrap(True)
        controls.addWidget(self.summary, 1)

        self.checkin = QPushButton("Check In")
        self.checkout = QPushButton("Check Out")
        self.add = QPushButton("Book Time")
        self.edit = QPushButton("Edit")
        self.delete = QPushButton("Delete")
        for button in (self.checkin, self.checkout):
            controls.addWidget(button)
        if self.management:
            for button in (self.add, self.edit, self.delete):
                controls.addWidget(button)
        root.addLayout(controls)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Start", "End", "Hours", "Work Type", "Source", "Status"]
        )
        configure_employee_table(
            self.table,
            WORKING_TIME_COLUMNS,
            row_height=36,
            minimum_height=280,
        )
        root.addWidget(self.table, 1)

        self.checkin.clicked.connect(self._check_in)
        self.checkout.clicked.connect(self._check_out)
        if self.management:
            self.add.clicked.connect(self._add)
            self.edit.clicked.connect(self._edit)
            self.delete.clicked.connect(self._delete)
        self.set_editable(self.editable)

    def set_editable(self, enabled):
        self.editable = bool(enabled)
        for button in (self.checkin, self.checkout):
            button.setEnabled(self.editable)
        if self.management:
            for button in (self.add, self.edit, self.delete):
                button.setEnabled(self.editable)

    def _range(self):
        q = self.month.date()
        y, m = q.year(), q.month()
        return date(y, m, 1), date(y, m, monthrange(y, m)[1])

    def _handle_error(self, title, exc):
        QMessageBox.warning(
            self,
            title,
            f"Operation failed.\n\nReason: {exc}\n\nSee application log for technical details.",
        )

    def refresh(self):
        def action():
            start, end = self._range()
            rows = self.service.list_entries(self.employee.id, start, end)
            self.table.setRowCount(0)
            for entry in rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                minutes = self.service._minutes(entry.start_time, entry.end_time)
                values = [
                    entry.work_date.strftime("%d/%m/%Y"),
                    entry.start_time.strftime("%H:%M"),
                    entry.end_time.strftime("%H:%M") if entry.end_time else "OPEN",
                    f"{minutes / 60:.2f}",
                    entry.work_type,
                    entry.source,
                    entry.status,
                ]
                set_employee_row(
                    self.table,
                    row,
                    values,
                    WORKING_TIME_COLUMNS,
                    row_user_data=entry.id,
                )

            summary = self.service.monthly_summary(self.employee.id, start.year, start.month)
            self.summary.setText(
                f"Actual {summary['actual_minutes']/60:.2f}h  •  "
                f"Expected {summary['expected_minutes']/60:.2f}h  •  "
                f"Overtime {summary['overtime_minutes']/60:.2f}h  •  "
                f"Shortfall {summary['shortfall_minutes']/60:.2f}h"
            )

        execute_ui_operation(
            logger_obj=logger,
            operation="working_time.refresh",
            action=action,
            on_error=lambda exc: self._handle_error("Working Time", exc),
            employee_id=self.employee.id,
            capability="working_time.view",
        )

    def _add(self):
        dialog = WorkingTimeBookingDialog(self, default_date=date.today())
        if dialog.exec():
            ok = execute_ui_operation(
                logger_obj=logger,
                operation="working_time.create_booking",
                action=lambda: self.service.create_booking(self.employee.id, *dialog.values()),
                on_error=lambda exc: self._handle_error("Working Time", exc),
                employee_id=self.employee.id,
                capability="working_time.manage",
            )
            if ok:
                self.refresh()

    def _edit(self):
        row = self.table.currentRow()
        if row < 0:
            return
        entry_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        def action():
            entry = next(e for e in self.service.list_entries(self.employee.id) if e.id == entry_id)
            dialog = WorkingTimeBookingDialog(self, entry)
            if dialog.exec():
                values = dialog.values()
                self.service.update_booking(
                    entry_id,
                    work_date=values[0],
                    start_time=values[1],
                    end_time=values[2],
                    work_type=values[3],
                    notes=values[4],
                )
                return True
            return False

        if execute_ui_operation(
            logger_obj=logger,
            operation="working_time.update_booking",
            action=action,
            on_error=lambda exc: self._handle_error("Working Time", exc),
            employee_id=self.employee.id,
            record_id=entry_id,
            capability="working_time.manage",
        ):
            self.refresh()

    def _delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        entry_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self,
            "Delete working time",
            "Delete selected working-time entry?",
        ) == QMessageBox.StandardButton.Yes:
            if execute_ui_operation(
                logger_obj=logger,
                operation="working_time.delete_entry",
                action=lambda: self.service.delete_entry(entry_id),
                on_error=lambda exc: self._handle_error("Working Time", exc),
                employee_id=self.employee.id,
                record_id=entry_id,
                capability="working_time.manage",
            ):
                self.refresh()

    def _check_in(self):
        if execute_ui_operation(
            logger_obj=logger,
            operation="working_time.check_in",
            action=lambda: self.service.check_in(self.employee.id),
            on_error=lambda exc: self._handle_error("Check In", exc),
            employee_id=self.employee.id,
            capability="working_time.create.self",
        ):
            self.refresh()

    def _check_out(self):
        def action():
            rows = self.service.list_entries(self.employee.id, date.today(), date.today())
            open_rows = [e for e in rows if e.status == EmployeeWorkingTimeEntry.STATUS_OPEN]
            if not open_rows:
                raise ValueError("No open working-time entry to check out.")
            if len(open_rows) > 1:
                raise ValueError(
                    "Multiple open working-time entries were found; check-out was blocked to protect data integrity."
                )
            self.service.check_out(open_rows[0].id)

        if execute_ui_operation(
            logger_obj=logger,
            operation="working_time.check_out",
            action=action,
            on_error=lambda exc: self._handle_error("Check Out", exc),
            employee_id=self.employee.id,
            capability="working_time.create.self",
        ):
            self.refresh()
