from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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


class EmployeeWorkRegistrationReviewPage(QWidget):
    """Manager overview: one row per employee/month; review happens in detail."""

    detail_requested = Signal(object)

    def __init__(self, employee_service, registration_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._rs = registration_service
        self._rows = []
        self._write_enabled = False
        self._setup()
        self.refresh()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(12)

        title = QLabel("Work Registrations")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(title)

        hint = QLabel(
            "Each employee has one monthly registration containing all availability blocks. "
            "Select an employee to review the complete registration."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#68737d;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        self.month = QLabel()
        self.month.setStyleSheet("font-size:15px;font-weight:600;")
        bar.addWidget(self.month)
        bar.addStretch()
        self.detail_btn = QPushButton("Open Detail")
        self.close_btn = QPushButton("Close Registration Month")
        self.refresh_btn = QPushButton("Refresh")
        for button in (self.detail_btn, self.close_btn, self.refresh_btn):
            bar.addWidget(button)
        root.addLayout(bar)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Employee", "Code", "Blocks", "Total Hours", "Status", "Submitted", "Accepted"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.detail_btn.clicked.connect(self.open_detail)
        self.refresh_btn.clicked.connect(self.refresh)
        self.close_btn.clicked.connect(self.close_month)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.cellDoubleClicked.connect(lambda *_: self.open_detail())
        self._update_actions()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._update_actions()

    def _period(self):
        return self._rs.next_month()

    def refresh(self):
        try:
            year, month = self._period()
            self.month.setText(f"Planning input: {month:02d}/{year} • Next month")
            self._rows = self._rs.list_all(year, month)
            self.table.setRowCount(0)
            for registration in self._rows:
                hours = sum(
                    (block.end_time.hour * 60 + block.end_time.minute)
                    - (block.start_time.hour * 60 + block.start_time.minute)
                    for block in registration.blocks
                ) / 60
                values = [
                    registration.employee.full_name or "-",
                    registration.employee.employee_code or "-",
                    str(len(registration.blocks)),
                    f"{hours:.2f}",
                    registration.status,
                    registration.submitted_at.strftime("%d/%m/%Y %H:%M")
                    if registration.submitted_at
                    else "-",
                    registration.accepted_at.strftime("%d/%m/%Y %H:%M")
                    if registration.accepted_at
                    else "-",
                ]
                row = self.table.rowCount()
                self.table.insertRow(row)
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
                self.table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole, registration.employee_id
                )
            self._update_actions()
        except Exception as exc:
            QMessageBox.warning(
                self, "Work Registrations", f"Could not load registrations.\n\n{exc}"
            )

    def _selected(self):
        row = self.table.currentRow()
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def _update_actions(self):
        registration = self._selected()
        self.detail_btn.setEnabled(registration is not None)
        all_accepted = bool(self._rows) and all(
            item.status == EmployeeWorkRegistration.STATUS_ACCEPTED for item in self._rows
        )
        self.close_btn.setEnabled(self._write_enabled and all_accepted)

    def open_detail(self):
        registration = self._selected()
        if registration is not None:
            self.detail_requested.emit(registration)

    def close_month(self):
        year, month = self._period()
        if QMessageBox.question(
            self,
            "Close registration month",
            f"Close the {month:02d}/{year} registration period after all registrations are accepted?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._rs.close_month(year, month)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Close Registration", str(exc))
