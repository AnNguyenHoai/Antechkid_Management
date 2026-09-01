from __future__ import annotations

from calendar import monthrange
from datetime import date

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
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.employee_work_registration import EmployeeWorkRegistration


class WorkRegistrationDialog(QDialog):
    """Create or edit one availability block."""

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
    """Employee self-service monthly availability registration."""

    def __init__(self, service, employee, editable=False, parent=None):
        super().__init__(parent)
        self.service = service
        self.employee = employee
        self.editable = bool(editable)
        self.registration = None
        self._setup()
        self.refresh()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        self.title = QLabel("My Work Registration")
        self.title.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(self.title)

        self.description = QLabel(
            "Register the days and time ranges you are available to work next month. "
            "Your registration is submitted as one monthly request for manager planning."
        )
        self.description.setWordWrap(True)
        self.description.setStyleSheet("color:#68737d;")
        root.addWidget(self.description)

        summary = QGroupBox("Registration Summary")
        summary_layout = QGridLayout(summary)
        self.month = QLabel("-")
        self.status = QLabel("-")
        self.blocks_summary = QLabel("0 blocks")
        self.hours_summary = QLabel("0.00 hours")
        self.deadline_summary = QLabel("-")
        self.status.setStyleSheet("font-weight:700;")
        summary_layout.addWidget(QLabel("Month"), 0, 0)
        summary_layout.addWidget(self.month, 0, 1)
        summary_layout.addWidget(QLabel("Status"), 0, 2)
        summary_layout.addWidget(self.status, 0, 3)
        summary_layout.addWidget(QLabel("Availability"), 1, 0)
        summary_layout.addWidget(self.blocks_summary, 1, 1)
        summary_layout.addWidget(QLabel("Total Hours"), 1, 2)
        summary_layout.addWidget(self.hours_summary, 1, 3)
        summary_layout.addWidget(QLabel("Submission Deadline"), 2, 0)
        summary_layout.addWidget(self.deadline_summary, 2, 1, 1, 3)
        root.addWidget(summary)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("padding:10px;border-radius:6px;")
        root.addWidget(self.message)

        actions = QHBoxLayout()
        self.add = QPushButton("+ Add Availability")
        self.edit = QPushButton("Edit")
        self.delete = QPushButton("Delete")
        self.submit = QPushButton("Submit for Planning")
        actions.addWidget(self.add)
        actions.addWidget(self.edit)
        actions.addWidget(self.delete)
        actions.addStretch()
        actions.addWidget(self.submit)
        root.addLayout(actions)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "From", "To", "Hours", "Work Type", "Notes"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.add.clicked.connect(self._add)
        self.edit.clicked.connect(self._edit)
        self.delete.clicked.connect(self._delete)
        self.submit.clicked.connect(self._submit_month)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.set_editable(self.editable)

    def _range(self):
        year, month = self.service.next_month()
        return year, month, date(year, month, 1), date(year, month, monthrange(year, month)[1])

    def set_editable(self, enabled):
        self.editable = bool(enabled)
        self._update_actions()

    def _is_draft(self):
        return self.registration is None or self.registration.status == EmployeeWorkRegistration.STATUS_DRAFT

    def _update_actions(self):
        can_edit = self.editable and self._is_draft()
        has_selection = self.table.currentRow() >= 0
        self.add.setEnabled(can_edit)
        self.edit.setEnabled(can_edit and has_selection)
        self.delete.setEnabled(can_edit and has_selection)
        self.submit.setEnabled(
            can_edit and bool(self.registration and self.registration.blocks)
        )
        self.table.setEnabled(True)

    def _set_status_message(self, status):
        if status == EmployeeWorkRegistration.STATUS_DRAFT:
            self.message.setText("Draft: you can add, edit, or remove availability before submitting.")
        elif status == EmployeeWorkRegistration.STATUS_SUBMITTED:
            self.message.setText(
                "Submitted for manager review. Your availability is read-only until a manager reopens it."
            )
        elif status == EmployeeWorkRegistration.STATUS_ACCEPTED:
            self.message.setText(
                "Accepted by manager. The registration is locked. Ask the manager to reopen it if you need to correct a mistake."
            )
        else:
            self.message.setText("")

    def refresh(self):
        try:
            if self.employee is None:
                raise ValueError("No employee profile is linked to this account.")

            year, month, first_day, last_day = self._range()
            self.month.setText(f"{month:02d}/{year} • Next month")
            self.registration = self.service.list_for_employee(self.employee.id, year, month)
            registration_status = (
                self.registration.status
                if self.registration
                else EmployeeWorkRegistration.STATUS_DRAFT
            )
            self.status.setText(registration_status)

            self.table.setRowCount(0)
            total_minutes = 0
            block_count = 0
            if self.registration:
                for block in self.registration.blocks:
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    minutes = (
                        block.end_time.hour * 60
                        + block.end_time.minute
                        - block.start_time.hour * 60
                        - block.start_time.minute
                    )
                    total_minutes += minutes
                    block_count += 1
                    values = [
                        block.work_date.strftime("%d/%m/%Y"),
                        block.start_time.strftime("%H:%M"),
                        block.end_time.strftime("%H:%M"),
                        f"{minutes / 60:.2f}",
                        block.work_type,
                        block.notes or "",
                    ]
                    for column, value in enumerate(values):
                        self.table.setItem(row, column, QTableWidgetItem(value))
                    self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, block.id)

            self.blocks_summary.setText(f"{block_count} block{'s' if block_count != 1 else ''}")
            self.hours_summary.setText(f"{total_minutes / 60:.2f} hours")

            try:
                period = self.service.get_period(year, month)
                deadline = getattr(period, "submission_deadline", None)
                self.deadline_summary.setText(
                    deadline.strftime("%d/%m/%Y") if deadline else "Not set"
                )
            except Exception:
                self.deadline_summary.setText("-")

            self._set_status_message(registration_status)
            self._update_actions()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Work Registration",
                f"Could not load your work registration.\n\n{exc}",
            )

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or not self.registration:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        block_id = item.data(Qt.ItemDataRole.UserRole)
        return next((block for block in self.registration.blocks if block.id == block_id), None)

    def _add(self):
        if not self.editable or not self._is_draft():
            return
        year, month, first_day, last_day = self._range()
        dialog = WorkRegistrationDialog(
            self,
            default_date=first_day,
            min_date=first_day,
            max_date=last_day,
        )
        if not dialog.exec():
            return
        try:
            self.service.create(self.employee.id, *dialog.values())
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Work Registration", str(exc))

    def _edit(self):
        block = self._selected()
        if block is None or not self.editable or not self._is_draft():
            return
        year, month, first_day, last_day = self._range()
        dialog = WorkRegistrationDialog(
            self,
            block,
            min_date=first_day,
            max_date=last_day,
        )
        if not dialog.exec():
            return
        try:
            value = dialog.values()
            self.service.update(
                block.id,
                work_date=value[0],
                start_time=value[1],
                end_time=value[2],
                work_type=value[3],
                notes=value[4],
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Work Registration", str(exc))

    def _delete(self):
        block = self._selected()
        if block is None or not self.editable or not self._is_draft():
            return
        if QMessageBox.question(
            self,
            "Delete availability",
            "Delete selected availability block?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(block.id)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Work Registration", str(exc))

    def _submit_month(self):
        year, month, _, _ = self._range()
        if not self.editable or not self._is_draft() or not self.registration:
            return
        if QMessageBox.question(
            self,
            "Submit availability",
            f"Submit the complete {month:02d}/{year} availability to the manager?\n\n"
            "You will not be able to edit it until a manager reopens the registration.",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.submit_month(self.employee.id, year, month)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Work Registration", str(exc))
