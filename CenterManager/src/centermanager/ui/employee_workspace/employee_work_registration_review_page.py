from __future__ import annotations

import logging
from datetime import timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QInputDialog,
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

from centermanager.core.current_user import get_current_user
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_admin_management_service import (
    EmployeeAdminManagementAccessDeniedError,
    EmployeeAdminManagementService,
    EmployeeAdminManagementValidationError,
)

logger = logging.getLogger(__name__)


class EmployeeWorkRegistrationReviewPage(QWidget):
    """Manager overview for next-week employee availability registrations."""

    detail_requested = Signal(object)

    def __init__(self, employee_service, registration_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._rs = registration_service
        self._rows = []
        self._filtered_rows = []
        self._selected_registration_id = None
        self._write_enabled = False
        self._period_status = EmployeeWorkRegistrationPeriod.STATUS_OPEN
        self._week_start = None
        self._admin_service = EmployeeAdminManagementService(
            getattr(registration_service, "_sf"),
            repository_provider=getattr(registration_service, "_repository_provider", None),
        )
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
            "Review employee availability for next week. "
            "Accept submitted registrations and close the week when all are accepted."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#68737d;")
        root.addWidget(hint)

        bar = QHBoxLayout()
        self.period_label = QLabel()
        self.period_label.setStyleSheet("font-size:15px;font-weight:600;")
        bar.addWidget(self.period_label)
        bar.addStretch()
        bar.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["ALL", "DRAFT", "SUBMITTED", "ACCEPTED"])
        self.status_filter.currentTextChanged.connect(self._apply_filter)
        bar.addWidget(self.status_filter)
        self.accept_btn = QPushButton("Accept")
        self.reopen_btn = QPushButton("Reopen")
        self.detail_btn = QPushButton("Open Detail")
        self.close_btn = QPushButton("Close Registration Week")
        self.reopen_period_btn = QPushButton("Re-open Closed Week")
        self.refresh_btn = QPushButton("Refresh")
        for button in (
            self.accept_btn,
            self.reopen_btn,
            self.detail_btn,
            self.close_btn,
            self.reopen_period_btn,
            self.refresh_btn,
        ):
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
        self.close_btn.clicked.connect(self.close_week)
        self.reopen_period_btn.clicked.connect(self.reopen_period)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.open_detail())
        self._update_actions()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._update_actions()

    @staticmethod
    def _is_admin() -> bool:
        user = get_current_user()
        return bool(
            user
            and getattr(getattr(user, "role", None), "name", None) == RoleDefinitions.ADMIN
        )

    @staticmethod
    def _hours(registration) -> float:
        total_minutes = sum(
            (block.end_time.hour * 60 + block.end_time.minute)
            - (block.start_time.hour * 60 + block.start_time.minute)
            for block in registration.blocks
        )
        return total_minutes / 60

    @staticmethod
    def _registration_identity(registration):
        registration_id = getattr(registration, "id", None)
        return ("registration", registration_id) if registration_id is not None else None

    def refresh(self):
        try:
            self._week_start = self._rs.next_week()
            period = self._rs.get_period(self._week_start)
            self._period_status = getattr(
                period, "status", EmployeeWorkRegistrationPeriod.STATUS_OPEN
            )
            week_end = self._week_start + timedelta(days=6)
            period_label = (
                "Closed"
                if self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
                else "Open"
            )
            self.period_label.setText(
                f"Planning input: {self._week_start:%d/%m/%Y} - "
                f"{week_end:%d/%m/%Y} • Next week • Period: {period_label}"
            )
            self._rows = self._rs.list_all(self._week_start)
            counts = {"DRAFT": 0, "SUBMITTED": 0, "ACCEPTED": 0}
            for registration in self._rows:
                counts[registration.status] = counts.get(registration.status, 0) + 1
            self.counters.setText(
                f"Total: {len(self._rows)} • Draft: {counts['DRAFT']} • "
                f"Submitted: {counts['SUBMITTED']} • Accepted: {counts['ACCEPTED']}"
            )
            self._apply_filter()
        except Exception as exc:
            logger.exception("[WORK_REGISTRATION_ERROR] weekly review refresh failed")
            QMessageBox.warning(
                self,
                "Work Registrations",
                f"Could not load next-week registrations.\n\n{exc}",
            )

    def _selection_changed(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._filtered_rows):
            self._selected_registration_id = self._registration_identity(
                self._filtered_rows[row]
            )
        else:
            self._selected_registration_id = None
        self._update_actions()

    def _apply_filter(self, *args):
        selected = self.status_filter.currentText()
        previous_id = self._selected_registration_id
        user_filter_change = bool(args)
        self._filtered_rows = (
            list(self._rows)
            if selected == "ALL"
            else [registration for registration in self._rows if registration.status == selected]
        )

        old_block_state = self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(0)
            for registration in self._filtered_rows:
                row = self.table.rowCount()
                self.table.insertRow(row)
                values = [
                    registration.employee.full_name or "-",
                    registration.employee.employee_code or "-",
                    str(len(registration.blocks)),
                    f"{self._hours(registration):.2f}",
                    registration.status,
                    registration.submitted_at.strftime("%d/%m/%Y %H:%M")
                    if registration.submitted_at
                    else "-",
                    registration.accepted_at.strftime("%d/%m/%Y %H:%M")
                    if registration.accepted_at
                    else "-",
                ]
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
                self.table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole,
                    self._registration_identity(registration),
                )

            self.table.clearSelection()
            self.table.setCurrentCell(-1, -1)
            target_row = next(
                (
                    index
                    for index, registration in enumerate(self._filtered_rows)
                    if self._registration_identity(registration) == previous_id
                ),
                None,
            )
            if target_row is not None:
                self.table.selectRow(target_row)
                self._selected_registration_id = previous_id
            elif previous_id is None and user_filter_change and self._filtered_rows:
                self.table.selectRow(0)
                self._selected_registration_id = self._registration_identity(
                    self._filtered_rows[0]
                )
            else:
                self._selected_registration_id = None
        finally:
            self.table.blockSignals(old_block_state)
        self._update_actions()

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._filtered_rows):
            return None
        return self._filtered_rows[row]

    def _update_actions(self):
        registration = self._selected() if hasattr(self, "table") else None
        period_closed = self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
        self.detail_btn.setEnabled(registration is not None)
        self.accept_btn.setEnabled(
            self._write_enabled
            and not period_closed
            and registration is not None
            and registration.status == EmployeeWorkRegistration.STATUS_SUBMITTED
        )
        self.reopen_btn.setEnabled(
            self._write_enabled
            and not period_closed
            and registration is not None
            and registration.status == EmployeeWorkRegistration.STATUS_ACCEPTED
        )
        all_accepted = bool(self._rows) and all(
            item.status == EmployeeWorkRegistration.STATUS_ACCEPTED for item in self._rows
        )
        self.close_btn.setEnabled(self._write_enabled and not period_closed and all_accepted)
        self.reopen_period_btn.setEnabled(
            self._write_enabled and self._is_admin() and period_closed
        )

    @staticmethod
    def _confirm(title, text):
        return QMessageBox.question(
            None,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes

    def accept_selected(self):
        registration = self._selected()
        if (
            not self._write_enabled
            or self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
            or registration is None
            or registration.status != EmployeeWorkRegistration.STATUS_SUBMITTED
        ):
            return
        if not self._confirm(
            "Accept Registration",
            "Accept this employee's next-week work registration?",
        ):
            return
        try:
            self._rs.accept(registration.employee_id, self._week_start)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Accept Registration", str(exc))

    def reopen_selected(self):
        registration = self._selected()
        if (
            not self._write_enabled
            or self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED
            or registration is None
            or registration.status != EmployeeWorkRegistration.STATUS_ACCEPTED
        ):
            return
        if not self._confirm(
            "Reopen Registration",
            "Reopen this weekly registration so the employee can correct it?",
        ):
            return
        try:
            self._rs.reopen(registration.employee_id, self._week_start)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Reopen Registration", str(exc))

    def open_detail(self):
        registration = self._selected()
        if registration is not None:
            self.detail_requested.emit(registration)

    @staticmethod
    def _ask_reason(parent, title, prompt):
        reason, accepted = QInputDialog.getText(parent, title, prompt)
        value = reason.strip() if accepted else ""
        return value if accepted and value else None

    def reopen_period(self):
        if (
            not self._write_enabled
            or not self._is_admin()
            or self._period_status != EmployeeWorkRegistrationPeriod.STATUS_CLOSED
            or self._week_start is None
        ):
            return
        reason = self._ask_reason(
            self,
            "Re-open Registration Week",
            "Reason for reopening this closed registration week:",
        )
        if not reason:
            return
        week_end = self._week_start + timedelta(days=6)
        if not self._confirm(
            "Confirm Period Re-open",
            f"Re-open {self._week_start:%d/%m/%Y} - {week_end:%d/%m/%Y}?\n\n"
            "Registration workflow states will not be changed.",
        ):
            return
        try:
            self._admin_service.reopen_period(self._week_start, reason=reason)
            self.refresh()
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            QMessageBox.warning(self, "Re-open Registration Week", str(exc))
        except Exception as exc:
            logger.exception("[WORK_REGISTRATION_ERROR] weekly period reopen failed")
            QMessageBox.critical(
                self,
                "Re-open Registration Week",
                f"Could not reopen the period.\n\n{exc}",
            )

    def close_week(self):
        if self._week_start is None:
            return
        if self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
            return
        week_end = self._week_start + timedelta(days=6)
        if not self._confirm(
            "Close registration week",
            f"Close {self._week_start:%d/%m/%Y} - {week_end:%d/%m/%Y} "
            "after all registrations are accepted?",
        ):
            return
        try:
            self._rs.close_week(self._week_start)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Close Registration", str(exc))
