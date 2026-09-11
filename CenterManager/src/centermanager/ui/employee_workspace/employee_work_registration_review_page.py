from __future__ import annotations

import logging

from PySide6.QtCore import QSignalBlocker, Qt, Signal
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

from centermanager.models.employee_work_registration import EmployeeWorkRegistration
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.models.role import RoleDefinitions
from centermanager.core.current_user import get_current_user
from centermanager.services.employee_admin_management_service import (
    EmployeeAdminManagementAccessDeniedError,
    EmployeeAdminManagementService,
    EmployeeAdminManagementValidationError,
)

logger = logging.getLogger(__name__)


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
        self._selected_registration_id = None
        self._selection_is_explicit = False
        self._selection_syncing = False
        self._allow_implicit_selection = False
        self._admin_service = EmployeeAdminManagementService(getattr(registration_service, "_sf"))
        self._period_status = EmployeeWorkRegistrationPeriod.STATUS_OPEN
        self._setup()
        self.refresh()
        self._allow_implicit_selection = True

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
        self.reopen_period_btn = QPushButton("Re-open Closed Month")
        self.refresh_btn = QPushButton("Refresh")
        for button in (self.accept_btn, self.reopen_btn, self.detail_btn, self.close_btn, self.reopen_period_btn, self.refresh_btn):
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
        self.reopen_period_btn.clicked.connect(self.reopen_period)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(lambda *_: self.open_detail())
        self._update_actions()

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._update_actions()

    @staticmethod
    def _is_admin():
        user = get_current_user()
        return bool(user and getattr(getattr(user, "role", None), "name", None) == RoleDefinitions.ADMIN)

    def _period(self):
        return self._rs.next_month()

    @staticmethod
    def _hours(registration):
        return sum(
            ((block.end_time.hour * 60 + block.end_time.minute)
             - (block.start_time.hour * 60 + block.start_time.minute))
            for block in registration.blocks
        ) / 60

    @staticmethod
    def _registration_identity(registration):
        """Return a stable identity for a registration across table rebuilds.

        Production ORM registrations always have a database ``id``.  The
        employee-id fallback keeps lightweight test doubles and legacy callers
        usable while the UI transitions to registration identity.
        """
        registration_id = getattr(registration, "id", None)
        if registration_id is not None:
            return ("registration", registration_id)
        return ("employee", getattr(registration, "employee_id", None))

    def _load_period_status(self, year, month):
        """Return the lifecycle state of the registration period."""
        period = self._rs.get_period(year, month)
        return getattr(period, "status", EmployeeWorkRegistrationPeriod.STATUS_OPEN)

    def refresh(self):
        try:
            user = get_current_user()
            logger.info(
                "[WORK_REGISTRATION_REVIEW] refresh start user_id=%s role=%s",
                getattr(user, "id", None),
                getattr(getattr(user, "role", None), "name", None),
            )
            year, month = self._period()
            self._period_status = self._load_period_status(year, month)
            period_label = "Closed" if self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED else "Open"
            self.month.setText(f"Planning input: {month:02d}/{year} • Next month • Period: {period_label}")
            self._rows = self._rs.list_all(year, month)
            counts = {"DRAFT": 0, "SUBMITTED": 0, "ACCEPTED": 0}
            for registration in self._rows:
                counts[registration.status] = counts.get(registration.status, 0) + 1
            self.counters.setText(
                f"Total: {len(self._rows)} • Draft: {counts['DRAFT']} • "
                f"Submitted: {counts['SUBMITTED']} • Accepted: {counts['ACCEPTED']}"
            )
            self._apply_filter()
            logger.info(
                "[WORK_REGISTRATION_REVIEW] refresh success user_id=%s year=%s month=%s rows=%s period_status=%s",
                getattr(user, "id", None), year, month, len(self._rows), self._period_status,
            )
        except Exception as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] review_refresh user_id=%s role=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None),
                getattr(getattr(get_current_user(), "role", None), "name", None),
                type(exc).__name__,
                exc,
            )
            QMessageBox.warning(
                self, "Work Registrations", f"Could not load registrations.\n\n{exc}"
            )

    def _apply_filter(self, *_):
        selected_registration_id = self._selected_registration_id
        preserve_selection = self._selection_is_explicit
        if not preserve_selection and hasattr(self, "table"):
            selected_rows = self.table.selectionModel().selectedRows(0)
            if selected_rows:
                selected_registration_id = selected_rows[0].data(Qt.ItemDataRole.UserRole)
                preserve_selection = selected_registration_id is not None

        selected = self.status_filter.currentText() if hasattr(self, "status_filter") else "ALL"
        filtered_rows = (
            list(self._rows) if selected == "ALL"
            else [r for r in self._rows if r.status == selected]
        )
        self._filtered_rows = filtered_rows

        signals_blocked = self.table.blockSignals(True)
        selection_model_blocker = QSignalBlocker(self.table.selectionModel())
        updates_enabled = self.table.updatesEnabled()
        self.table.setUpdatesEnabled(False)
        self._selection_syncing = True
        try:
            self.table.clearContents()
            self.table.setRowCount(0)

            target_row = None
            if preserve_selection and selected_registration_id is not None:
                for index, registration in enumerate(self._filtered_rows):
                    if self._registration_identity(registration) == selected_registration_id:
                        target_row = index
                        break

            if (
                target_row is None
                and not preserve_selection
                and self._allow_implicit_selection
                and self._filtered_rows
            ):
                target_row = 0

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
                self.table.item(row, 0).setData(
                    Qt.ItemDataRole.UserRole, self._registration_identity(registration)
                )

            if target_row is not None:
                self.table.selectRow(target_row)
                self._selected_registration_id = self._registration_identity(self._filtered_rows[target_row])
                self._selection_is_explicit = preserve_selection and (
                    self._registration_identity(self._filtered_rows[target_row]) == selected_registration_id
                )
            else:
                self.table.clearSelection()
                self._selected_registration_id = None
                self._selection_is_explicit = False
        finally:
            self._selection_syncing = False
            self.table.setUpdatesEnabled(updates_enabled)
            self.table.blockSignals(signals_blocked)
            del selection_model_blocker

        self._update_actions()

    def _on_selection_changed(self):
        if self._selection_syncing:
            return

        selected_rows = self.table.selectionModel().selectedRows(0)
        if not selected_rows:
            self._selected_registration_id = None
            self._selection_is_explicit = False
        else:
            registration_id = selected_rows[0].data(Qt.ItemDataRole.UserRole)
            self._selected_registration_id = registration_id
            self._selection_is_explicit = registration_id is not None
        self._update_actions()

    def _selected(self):
        registration_id = self._selected_registration_id
        if registration_id is None:
            return None

        return next(
            (
                registration
                for registration in self._filtered_rows
                if self._registration_identity(registration) == registration_id
            ),
            None,
        )

    def _update_actions(self):
        registration = self._selected()
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
        self.reopen_period_btn.setEnabled(self._write_enabled and self._is_admin() and period_closed)

    def _confirm(self, title, text):
        return QMessageBox.question(
            self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def accept_selected(self):
        registration = self._selected()
        if not self._write_enabled or self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED or not registration or registration.status != EmployeeWorkRegistration.STATUS_SUBMITTED:
            return
        if not self._confirm("Accept Registration", "Accept this employee's monthly work registration?"):
            return
        try:
            year, month = self._period()
            self._rs.accept(registration.employee_id, year, month)
            self.refresh()
        except Exception as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] operation=accept_selected user_id=%s employee_id=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None), getattr(registration, "employee_id", None), type(exc).__name__, exc,
            )
            QMessageBox.warning(self, "Accept Registration", str(exc))

    def reopen_selected(self):
        registration = self._selected()
        if not self._write_enabled or self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED or not registration or registration.status != EmployeeWorkRegistration.STATUS_ACCEPTED:
            return
        if not self._confirm("Reopen Registration", "Reopen this registration so the employee can correct it?"):
            return
        try:
            year, month = self._period()
            self._rs.reopen(registration.employee_id, year, month)
            self.refresh()
        except Exception as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] operation=reopen_selected user_id=%s employee_id=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None), getattr(registration, "employee_id", None), type(exc).__name__, exc,
            )
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
        if not self._write_enabled or not self._is_admin():
            return
        year, month = self._period()
        if self._period_status != EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
            return
        reason = self._ask_reason(
            self,
            "Re-open Registration Month",
            "Reason for reopening this closed registration month:",
        )
        if not reason:
            return
        if not self._confirm(
            "Confirm Period Re-open",
            f"Re-open the {month:02d}/{year} registration period?\n\n"
            "Registration workflow states will not be changed.",
        ):
            return
        try:
            self._admin_service.reopen_period(year, month, reason=reason)
            self.refresh()
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] operation=reopen_period user_id=%s year=%s month=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None), year, month, type(exc).__name__, exc,
            )
            QMessageBox.warning(self, "Re-open Registration Month", str(exc))
        except Exception as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] operation=reopen_period user_id=%s year=%s month=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None), year, month, type(exc).__name__, exc,
            )
            QMessageBox.critical(self, "Re-open Registration Month", f"Could not reopen the period.\n\n{exc}")

    def close_month(self):
        year, month = self._period()
        if self._period_status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED:
            return
        if not self._confirm(
            "Close registration month",
            f"Close the {month:02d}/{year} registration period after all registrations are accepted?",
        ):
            return
        try:
            self._rs.close_month(year, month)
            self.refresh()
        except Exception as exc:
            logger.exception(
                "[WORK_REGISTRATION_ERROR] operation=close_month user_id=%s year=%s month=%s exception_type=%s exception=%s",
                getattr(get_current_user(), "id", None), year, month, type(exc).__name__, exc,
            )
            QMessageBox.warning(self, "Close Registration", str(exc))
