from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.employee_work_registration import EmployeeWorkRegistration


class EmployeeWorkRegistrationDetailPage(QWidget):
    """Manager detail view for one employee's monthly work registration."""

    def __init__(self, registration_service, registration, parent=None):
        super().__init__(parent)
        self._rs = registration_service
        self.registration = registration
        self._write_enabled = False
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
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for column in range(5):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.accept_btn = QPushButton("Accept")
        self.reopen_btn = QPushButton("Reopen")
        actions.addWidget(self.back_btn)
        actions.addStretch()
        actions.addWidget(self.accept_btn)
        actions.addWidget(self.reopen_btn)
        root.addLayout(actions)

        self.back_btn.clicked.connect(self._back)
        self.accept_btn.clicked.connect(self._accept)
        self.reopen_btn.clicked.connect(self._reopen)

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._update_actions()

    def refresh(self) -> None:
        r = self.registration
        employee = getattr(r, "employee", None)
        name = getattr(employee, "full_name", None) or "-"
        code = getattr(employee, "employee_code", None) or "-"
        period = getattr(r, "period", None)
        if period:
            period_text = f"{period.month:02d}/{period.year}"
        else:
            period_text = "-"

        self.title.setText(f"{name} • Registration Detail")
        self.summary.setText(
            f"Employee: {name} ({code})\n"
            f"Registration month: {period_text}\n"
            f"Availability blocks: {len(r.blocks)}"
        )
        self.status.setText(f"Status: {r.status}")

        self.table.setRowCount(0)
        total_minutes = 0
        for block in sorted(r.blocks, key=lambda b: (b.work_date, b.start_time)):
            minutes = (
                block.end_time.hour * 60
                + block.end_time.minute
                - block.start_time.hour * 60
                - block.start_time.minute
            )
            total_minutes += minutes
            row = self.table.rowCount()
            self.table.insertRow(row)
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

        self.table.setToolTip(f"Total availability: {total_minutes / 60:.2f} hours")
        self._update_actions()

    def _update_actions(self) -> None:
        r = self.registration
        self.accept_btn.setEnabled(
            self._write_enabled
            and r.status == EmployeeWorkRegistration.STATUS_SUBMITTED
        )
        self.reopen_btn.setEnabled(
            self._write_enabled
            and r.status == EmployeeWorkRegistration.STATUS_ACCEPTED
        )

    def _period_values(self):
        period = getattr(self.registration, "period", None)
        if period is None:
            raise ValueError("Registration period is unavailable.")
        return period.year, period.month

    def _accept(self):
        if not self._write_enabled:
            return
        try:
            year, month = self._period_values()
            self._rs.accept(self.registration.employee_id, year, month)
            self.registration = self._rs.list_for_employee(
                self.registration.employee_id, year, month
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Accept Registration", str(exc))

    def _reopen(self):
        if not self._write_enabled:
            return
        try:
            year, month = self._period_values()
            self._rs.reopen(self.registration.employee_id, year, month)
            self.registration = self._rs.list_for_employee(
                self.registration.employee_id, year, month
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Reopen Registration", str(exc))

    def _back(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "close_registration_detail"):
            parent.close_registration_detail()
