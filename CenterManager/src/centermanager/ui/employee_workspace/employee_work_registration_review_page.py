from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
    """Manager overview: filter and process monthly employee registrations."""

    detail_requested = Signal(object)

    def __init__(self, employee_service, registration_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._rs = registration_service
        self._rows = []
        self._filtered_rows = []
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
            "Review employee availability registrations for the next month. "
            "Filter by status, process submissions, or open the full detail."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#68737d;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        self.month = QLabel()
        self.month.setStyleSheet("font-size:15px;font-weight:600;")
        bar.addWidget(self.month)
        bar.addStretch()
        bar.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["ALL", "DRAFT", "SUBMITTED", "ACCEPTED"])
        self.status_filter.currentTextChanged.connect(self._apply_filter)
        bar.addWidget(self.status_filter)
        self.accept_btn = QPushButton("Accept")
        self.reopen_btn = QPushButton("Reopen")
        self.detail_btn = QPushButton("Open Detail")
        self.close_btn = QPushButton("Close Registration Month")
        self.refresh_btn = QPushButton("Refresh")
        for button in (self.accept_btn, self.reopen_btn, self.detail_btn, self.close_btn, self.refresh_btn):
            bar.addWidget(button)
        root.addLayout(bar)

        self.counters = QLabel("Total: 0 • Draft: 0 • Submitted: 0 • Accepted: 0")
        self.counters.setStyleSheet("font-weight:600;")
        root.addWidget(self.counters)

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
        self.accept_btn.clicked.connect(self.accept_selected)
        self.reopen_btn.clicked.connect(self.reopen_selected)
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

    @staticmethod
    def _hours(registration):
        return sum(
            ((block.end_time.hour * 60 + block.end_time.minute)
             - (block.start_time.hour * 60 + block.start_time.minute))
            for block in registration.blocks
        ) / 60

    def refresh(self):
        try:
            year, month = self._period()
            self.month.setText(f"Planning input: {month:02d}/{year} • Next month")
            self._rows = self._rs.list_all(year, month)
            counts = {"DRAFT": 0, "SUBMITTED": 0, "ACCEPTED": 0}
            for registration in self._rows:
                counts[registration.status] = counts.get(registration.status, 0) + 1
            self.counters.setText(
                f"Total: {len(self._rows)} • Draft: {counts['DRAFT']} • "
                f"Submitted: {counts['SUBMITTED']} • Accepted: {counts['ACCEPTED']}"
            )
            self._apply_filter()
        except Exception as exc:
            QMessageBox.warning(
                self, "Work Registrations", f"Could not load registrations.\n\n{exc}"
            )

    def _apply_filter(self, *_):
        selected_employee_id = None
        current_row = self.table.currentRow()
        if 0 <= current_row < self.table.rowCount():
            selected_employee_id = self.table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)

        selected = self.status_filter.currentText() if hasattr(self, "status_filter") else "ALL"
        filtered_rows = (
            list(self._rows) if selected == "ALL"
            else [r for r in self._rows if r.status == selected]
        )
        self._filtered_rows = filtered_rows

        # Rebuilding a QTableWidget emits selection/item signals while its
        # internal model is being mutated.  In this page those signals feed
        # _update_actions(), which reads the same model.  Keep the rebuild
        # atomic from Qt's signal/paint perspective and update actions once at
        # the end.  This also makes refresh/filter deterministic in tests and
        # in the live UI.
        signals_blocked = self.table.blockSignals(True)
        updates_enabled = self.table.updatesEnabled()
        self.table.setUpdatesEnabled(False)
        try:
            self.table.clearContents()
            self.table.setRowCount(0)
            restored = False
            for registration in self._filtered_rows:
                values = [
                    registration.employee.full_name or "-",
                    registration.employee.employee_code or "-",
                    str(len(registration.blocks)),
                    f"{self._hours(registration):.2f}",
                    registration.status,
                    registration.submitted_at.strftime("%d/%m/%Y %H:%M") if registration.submitted_at else "-",
                    registration.accepted_at.strftime("%d/%m/%Y %H:%M") if registration.accepted_at else "-",
                ]
                row = self.table.rowCount()
                self.table.insertRow(row)
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
                self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, registration.employee_id)
                if registration.employee_id == selected_employee_id:
                    self.table.selectRow(row)
                    restored = True

            if not restored and self._filtered_rows and selected_employee_id is None:
                self.table.selectRow(0)
        finally:
            self.table.setUpdatesEnabled(updates_enabled)
            self.table.blockSignals(signals_blocked)

        self._update_actions()

    def _selected(self):
        row = self.table.currentRow()
        if not 0 <= row < self.table.rowCount():
            return None
        employee_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        return next(
            (registration for registration in self._filtered_rows if registration.employee_id == employee_id),
            None,
        )

    def _update_actions(self):
        registration = self._selected()
        self.detail_btn.setEnabled(registration is not None)
        self.accept_btn.setEnabled(
            self._write_enabled
            and registration is not None
            and registration.status == EmployeeWorkRegistration.STATUS_SUBMITTED
        )
        self.reopen_btn.setEnabled(
            self._write_enabled
            and registration is not None
            and registration.status == EmployeeWorkRegistration.STATUS_ACCEPTED
        )
        all_accepted = bool(self._rows) and all(
            item.status == EmployeeWorkRegistration.STATUS_ACCEPTED for item in self._rows
        )
        self.close_btn.setEnabled(self._write_enabled and all_accepted)

    def _confirm(self, title, text):
        return QMessageBox.question(
            self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def accept_selected(self):
        registration = self._selected()
        if not self._write_enabled or not registration or registration.status != EmployeeWorkRegistration.STATUS_SUBMITTED:
            return
        if not self._confirm("Accept Registration", "Accept this employee's monthly work registration?"):
            return
        try:
            year, month = self._period()
            self._rs.accept(registration.employee_id, year, month)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Accept Registration", str(exc))

    def reopen_selected(self):
        registration = self._selected()
        if not self._write_enabled or not registration or registration.status != EmployeeWorkRegistration.STATUS_ACCEPTED:
            return
        if not self._confirm("Reopen Registration", "Reopen this registration so the employee can correct it?"):
            return
        try:
            year, month = self._period()
            self._rs.reopen(registration.employee_id, year, month)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Reopen Registration", str(exc))

    def open_detail(self):
        registration = self._selected()
        if registration is not None:
            self.detail_requested.emit(registration)

    def close_month(self):
        year, month = self._period()
        if not self._confirm(
            "Close registration month",
            f"Close the {month:02d}/{year} registration period after all registrations are accepted?",
        ):
            return
        try:
            self._rs.close_month(year, month)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Close Registration", str(exc))
