from __future__ import annotations

import logging
from datetime import date, timedelta

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.ui.employee_workspace.table_layout import (
    CENTER,
    LEFT,
    RIGHT,
    EmployeeTableColumn,
    configure_employee_table,
    set_employee_row,
)

logger = logging.getLogger(__name__)


REGISTRATION_COLUMNS = [
    EmployeeTableColumn("fixed", 118, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 82, CENTER),
    EmployeeTableColumn("fixed", 78, RIGHT),
    EmployeeTableColumn("fixed", 118, CENTER),
    EmployeeTableColumn("stretch", None, LEFT),
]


class WorkRegistrationDialog(QDialog):
    def __init__(self, parent=None, entry=None, default_date=None, min_date=None, max_date=None):
        super().__init__(parent)
        self.setWindowTitle("Register Availability" if entry is None else "Edit Availability")
        self.setMinimumWidth(430)
        form = QFormLayout(self)

        self.day = QDateEdit()
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("dd/MM/yyyy")
        d = default_date or date.today()
        self.day.setDate(QDate(d.year, d.month, d.day))
        if min_date:
            self.day.setMinimumDate(QDate(min_date.year, min_date.month, min_date.day))
        if max_date:
            self.day.setMaximumDate(QDate(max_date.year, max_date.month, max_date.day))

        self.start = QTimeEdit()
        self.start.setDisplayFormat("HH:mm")
        self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit()
        self.end.setDisplayFormat("HH:mm")
        self.end.setTime(QTime(17, 0))
        self.typ = QComboBox()
        self.typ.addItems(["WORK", "TEACHING", "MEETING", "TRAINING", "ADMIN", "OTHER"])
        self.notes = QLineEdit()
        self.notes.setMaxLength(500)
        self.notes.setPlaceholderText("Optional note")

        for label, widget in (
            ("Available date", self.day),
            ("From", self.start),
            ("To", self.end),
            ("Work type", self.typ),
            ("Note", self.notes),
        ):
            form.addRow(label, widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        if entry:
            self.day.setDate(QDate(entry.work_date.year, entry.work_date.month, entry.work_date.day))
            self.start.setTime(QTime(entry.start_time.hour, entry.start_time.minute))
            self.end.setTime(QTime(entry.end_time.hour, entry.end_time.minute))
            self.typ.setCurrentText(entry.work_type)
            self.notes.setText(entry.notes or "")

    def _accept_if_valid(self):
        if self.start.time() >= self.end.time():
            QMessageBox.warning(self, "Invalid availability", "End time must be after start time.")
            return
        self.accept()

    def values(self):
        return (
            self.day.date().toPython(),
            self.start.time().toPython(),
            self.end.time().toPython(),
            self.typ.currentText(),
            self.notes.text().strip() or None,
        )


class EmployeeWorkRegistrationWidget(QWidget):
    """Employee self-service weekly availability registration."""

    def __init__(self, service, employee, editable=False, parent=None):
        super().__init__(parent)
        self.service = service
        self.employee = employee
        self.editable = bool(editable)
        self.registration = None
        self._last_error = None
        self._setup()
        self.refresh()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("My Work Registration")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(title)

        desc = QLabel(
            "Register the days and time ranges you are available to work next week. "
            "Your registration is submitted as one weekly request for manager planning."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#68737d;")
        root.addWidget(desc)

        summary = QGroupBox("Registration Summary")
        grid = QGridLayout(summary)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        self.week = QLabel("-")
        self.status = QLabel("-")
        self.blocks_summary = QLabel("0 blocks")
        self.hours_summary = QLabel("0.00 hours")
        self.deadline_summary = QLabel("-")
        self.status.setStyleSheet("font-weight:700;")
        grid.addWidget(QLabel("Week"), 0, 0)
        grid.addWidget(self.week, 0, 1)
        grid.addWidget(QLabel("Status"), 0, 2)
        grid.addWidget(self.status, 0, 3)
        grid.addWidget(QLabel("Availability"), 1, 0)
        grid.addWidget(self.blocks_summary, 1, 1)
        grid.addWidget(QLabel("Total Hours"), 1, 2)
        grid.addWidget(self.hours_summary, 1, 3)
        grid.addWidget(QLabel("Submission Deadline"), 2, 0)
        grid.addWidget(self.deadline_summary, 2, 1, 1, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        root.addWidget(summary)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(42)
        root.addWidget(self.message)

        actions = QHBoxLayout()
        self.add = QPushButton("+ Add Availability")
        self.edit = QPushButton("Edit")
        self.delete = QPushButton("Delete")
        self.submit = QPushButton("Submit Week for Planning")
        for button in (self.add, self.edit, self.delete):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(self.submit)
        root.addLayout(actions)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "From", "To", "Hours", "Work Type", "Notes"])
        configure_employee_table(
            self.table,
            REGISTRATION_COLUMNS,
            row_height=36,
            minimum_height=280,
        )
        root.addWidget(self.table, 1)

        self.add.clicked.connect(self._add)
        self.edit.clicked.connect(self._edit)
        self.delete.clicked.connect(self._delete)
        self.submit.clicked.connect(self._submit_week)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.set_editable(self.editable)

    def _range(self):
        start = self.service.next_week()
        return start, start + timedelta(days=6)

    def set_editable(self, enabled):
        self.editable = bool(enabled)
        self._update_actions()

    def _is_draft(self):
        return self.registration is None or self.registration.status == EmployeeWorkRegistration.STATUS_DRAFT

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or not self.registration:
            return None
        block_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next((block for block in self.registration.blocks if block.id == block_id), None)

    def _update_actions(self):
        can_edit = self.editable and self._is_draft()
        selected = self._selected() is not None
        self.add.setEnabled(can_edit)
        self.edit.setEnabled(can_edit and selected)
        self.delete.setEnabled(can_edit and selected)
        self.submit.setEnabled(can_edit and bool(self.registration and self.registration.blocks))

    def refresh(self):
        try:
            start, end = self._range()
            self.week.setText(f"{start:%d/%m/%Y} – {end:%d/%m/%Y} • Next week")
            self.registration = self.service.list_for_employee(self.employee.id, start)
            status = (
                self.registration.status
                if self.registration
                else EmployeeWorkRegistration.STATUS_DRAFT
            )
            self.status.setText(status)
            self.table.setRowCount(0)
            minutes = 0

            if self.registration:
                for block in sorted(
                    self.registration.blocks,
                    key=lambda item: (item.work_date, item.start_time),
                ):
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    duration = (
                        block.end_time.hour * 60 + block.end_time.minute
                    ) - (
                        block.start_time.hour * 60 + block.start_time.minute
                    )
                    minutes += duration
                    values = [
                        block.work_date.strftime("%d/%m/%Y"),
                        block.start_time.strftime("%H:%M"),
                        block.end_time.strftime("%H:%M"),
                        f"{duration/60:.2f}",
                        block.work_type,
                        block.notes or "",
                    ]
                    set_employee_row(
                        self.table,
                        row,
                        values,
                        REGISTRATION_COLUMNS,
                        row_user_data=block.id,
                    )

            count = len(self.registration.blocks) if self.registration else 0
            self.blocks_summary.setText(f"{count} block{'s' if count != 1 else ''}")
            self.hours_summary.setText(f"{minutes/60:.2f} hours")
            period = self.service.get_period(start)
            self.deadline_summary.setText(
                period.submission_deadline.strftime("%d/%m/%Y")
                if period.submission_deadline
                else "Not set"
            )
            self.message.setText(
                {
                    "DRAFT": "Draft: you can edit this week's availability before submitting.",
                    "SUBMITTED": "Submitted for manager review. This week is read-only until reopened.",
                    "ACCEPTED": "Accepted by manager. This week's registration is locked.",
                }.get(status, "")
            )
            self._update_actions()
        except Exception as exc:
            self.registration = None
            self.message.setText(f"Could not load your work registration. {exc}")
            logger.exception("weekly registration refresh failed")
            self._update_actions()

    def _mutate(self, fn, title):
        try:
            fn()
        except Exception as exc:
            QMessageBox.warning(self, title, str(exc))
        finally:
            self.refresh()

    def _add(self):
        start, end = self._range()
        dialog = WorkRegistrationDialog(
            self,
            default_date=start,
            min_date=start,
            max_date=end,
        )
        if dialog.exec():
            self._mutate(
                lambda: self.service.create(
                    self.employee.id,
                    *dialog.values(),
                    week_start=start,
                ),
                "Work Registration",
            )

    def _edit(self):
        block = self._selected()
        if not block:
            return
        start, end = self._range()
        dialog = WorkRegistrationDialog(self, block, min_date=start, max_date=end)
        if dialog.exec():
            values = dialog.values()
            self._mutate(
                lambda: self.service.update(
                    block.id,
                    work_date=values[0],
                    start_time=values[1],
                    end_time=values[2],
                    work_type=values[3],
                    notes=values[4],
                ),
                "Work Registration",
            )

    def _delete(self):
        block = self._selected()
        if block and QMessageBox.question(
            self,
            "Delete availability",
            "Delete selected availability block?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._mutate(lambda: self.service.delete(block.id), "Work Registration")

    def _submit_week(self):
        start, end = self._range()
        if self.registration and QMessageBox.question(
            self,
            "Submit availability",
            f"Submit availability for {start:%d/%m/%Y} – {end:%d/%m/%Y}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._mutate(
                lambda: self.service.submit_week(self.employee.id, start),
                "Submit Availability",
            )
