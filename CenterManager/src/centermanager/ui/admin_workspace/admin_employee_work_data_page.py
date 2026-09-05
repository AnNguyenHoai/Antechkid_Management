from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QInputDialog, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from centermanager.models.employee_work_registration_period import EmployeeWorkRegistrationPeriod
from centermanager.models.role import RoleDefinitions
from centermanager.services.employee_admin_management_service import (
    EmployeeAdminManagementAccessDeniedError,
    EmployeeAdminManagementService,
    EmployeeAdminManagementValidationError,
)
from centermanager.services.employee_service import EmployeeService
from centermanager.services.employee_work_registration_service import EmployeeWorkRegistrationService
from centermanager.core.current_user import get_current_user


class AdminEmployeeWorkDataPage(QWidget):
    """Admin-only UI for employee deletion and registration-period overrides."""

    def __init__(self, session_factory, notification_service=None, parent=None):
        super().__init__(parent)
        self._session_factory = session_factory
        self._notification_service = notification_service
        self._employee_service = EmployeeService(session_factory)
        self._registration_service = EmployeeWorkRegistrationService(session_factory)
        self._admin_service = EmployeeAdminManagementService(session_factory)
        self._write_enabled = True
        self._employees = []
        self._registrations = []
        self._period_initialized = False
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        title = QLabel("Employee & Work Registration Management")
        title.setStyleSheet("font-size:24px;font-weight:700;")
        root.addWidget(title)
        hint = QLabel("Admin can override closed registration periods and remove employee or registration data. Every destructive or override action requires a reason and is audited.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#68737d;")
        root.addWidget(hint)
        self._build_employee_section(root)
        self._build_period_section(root)
        root.addStretch()

    def _build_employee_section(self, root):
        header = QHBoxLayout()
        label = QLabel("Employees")
        label.setStyleSheet("font-size:18px;font-weight:700;")
        header.addWidget(label); header.addStretch()
        self.employee_refresh_btn = QPushButton("Refresh")
        self.employee_delete_btn = QPushButton("Delete Employee")
        self.employee_delete_btn.setToolTip("Hard-delete only an employee with no operational history.")
        header.addWidget(self.employee_refresh_btn); header.addWidget(self.employee_delete_btn)
        root.addLayout(header)
        self.employee_table = QTableWidget(0, 5)
        self.employee_table.setHorizontalHeaderLabels(["Code", "Name", "Position", "Status", "Account"])
        self.employee_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.employee_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.employee_table.verticalHeader().setVisible(False)
        root.addWidget(self.employee_table, 1)
        self.employee_refresh_btn.clicked.connect(self.refresh_employees)
        self.employee_delete_btn.clicked.connect(self.delete_selected_employee)
        self.employee_table.itemSelectionChanged.connect(self._update_employee_actions)

    def _build_period_section(self, root):
        header = QHBoxLayout()
        label = QLabel("Registration Period Override")
        label.setStyleSheet("font-size:18px;font-weight:700;")
        header.addWidget(label); header.addStretch(); header.addWidget(QLabel("Year:"))
        self.year = QSpinBox(); self.year.setRange(2000, 2100); header.addWidget(self.year)
        header.addWidget(QLabel("Month:"))
        self.month = QComboBox()
        for value in range(1, 13): self.month.addItem(f"{value:02d}", value)
        header.addWidget(self.month)
        self.period_refresh_btn = QPushButton("Load Period")
        self.reopen_period_btn = QPushButton("Re-open Closed Period")
        header.addWidget(self.period_refresh_btn); header.addWidget(self.reopen_period_btn)
        root.addLayout(header)
        self.period_status = QLabel("Period: -")
        self.period_status.setStyleSheet("font-weight:600;")
        root.addWidget(self.period_status)
        self.registration_table = QTableWidget(0, 5)
        self.registration_table.setHorizontalHeaderLabels(["Employee", "Code", "Status", "Blocks", "Registration ID"])
        self.registration_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.registration_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.registration_table.verticalHeader().setVisible(False)
        root.addWidget(self.registration_table, 1)
        actions = QHBoxLayout(); actions.addStretch()
        self.registration_delete_btn = QPushButton("Delete Registration")
        self.registration_delete_btn.setToolTip("Delete the selected registration aggregate. Audit history is retained.")
        actions.addWidget(self.registration_delete_btn); root.addLayout(actions)
        self.period_refresh_btn.clicked.connect(self.refresh_period)
        self.month.currentIndexChanged.connect(self.refresh_period)
        self.year.valueChanged.connect(self.refresh_period)
        self.reopen_period_btn.clicked.connect(self.reopen_period)
        self.registration_delete_btn.clicked.connect(self.delete_selected_registration)
        self.registration_table.itemSelectionChanged.connect(self._update_registration_actions)

    @staticmethod
    def _is_admin():
        user = get_current_user()
        return bool(user and getattr(getattr(user, "role", None), "name", None) == RoleDefinitions.ADMIN)

    def set_write_enabled(self, enabled):
        self._write_enabled = bool(enabled)
        self._update_employee_actions(); self._update_registration_actions()
        self.reopen_period_btn.setEnabled(self._write_enabled and self._is_admin() and self._period_is_closed())

    def _period_is_closed(self):
        return self.period_status.text().endswith(f"• {EmployeeWorkRegistrationPeriod.STATUS_CLOSED}")

    def _selected_employee(self):
        rows = self.employee_table.selectionModel().selectedRows()
        if not rows: return None
        row = rows[0].row()
        return self._employees[row] if 0 <= row < len(self._employees) else None

    def _selected_registration(self):
        rows = self.registration_table.selectionModel().selectedRows()
        if not rows: return None
        row = rows[0].row()
        return self._registrations[row] if 0 <= row < len(self._registrations) else None

    def _update_employee_actions(self):
        self.employee_delete_btn.setEnabled(self._write_enabled and self._is_admin() and self._selected_employee() is not None)

    def _update_registration_actions(self):
        self.registration_delete_btn.setEnabled(self._write_enabled and self._is_admin() and self._selected_registration() is not None)

    def refresh(self):
        if not self._period_initialized:
            self._set_default_period()
        self.refresh_employees()
        self.refresh_period()

    def refresh_employees(self):
        try:
            self._employees = self._employee_service.list_visible_employees()
            self.employee_table.setRowCount(0)
            for employee in self._employees:
                row = self.employee_table.rowCount(); self.employee_table.insertRow(row)
                values = [employee.employee_code or "-", employee.full_name or "-", employee.position or "-", (employee.employment_status or "-").replace("_", " "), employee.user.username if employee.user else "NOT LINKED"]
                for column, value in enumerate(values): self.employee_table.setItem(row, column, QTableWidgetItem(str(value)))
            self._update_employee_actions()
        except Exception as exc:
            self._employees = []; self.employee_table.setRowCount(0)
            QMessageBox.warning(self, "Employees", f"Could not load employees.\n\n{exc}")

    def _set_default_period(self):
        year, month = self._registration_service.next_month()
        with QSignalBlocker(self.year), QSignalBlocker(self.month):
            self.year.setValue(year)
            self.month.setCurrentIndex(month - 1)
        self._period_initialized = True

    def refresh_period(self):
        year, month = self.year.value(), self.month.currentData()
        if month is None: return
        try:
            period = self._registration_service.get_period(year, month)
            status = getattr(period, "status", EmployeeWorkRegistrationPeriod.STATUS_OPEN)
            self.period_status.setText(f"Period: {month:02d}/{year} • {status}")
            self.reopen_period_btn.setEnabled(self._write_enabled and self._is_admin() and status == EmployeeWorkRegistrationPeriod.STATUS_CLOSED)
            self._registrations = self._registration_service.list_all(year, month)
            self.registration_table.setRowCount(0)
            for registration in self._registrations:
                row = self.registration_table.rowCount(); self.registration_table.insertRow(row)
                employee = getattr(registration, "employee", None)
                values = [getattr(employee, "full_name", "-") or "-", getattr(employee, "employee_code", "-") or "-", registration.status, str(len(registration.blocks)), str(registration.id)]
                for column, value in enumerate(values): self.registration_table.setItem(row, column, QTableWidgetItem(str(value)))
            self._update_registration_actions()
        except Exception as exc:
            self._registrations = []; self.registration_table.setRowCount(0); self.reopen_period_btn.setEnabled(False)
            QMessageBox.warning(self, "Registration Period", f"Could not load registration period.\n\n{exc}")

    @staticmethod
    def _ask_reason(parent, title, prompt):
        reason, accepted = QInputDialog.getText(parent, title, prompt)
        reason = reason.strip() if accepted else ""
        return reason if accepted and reason else None

    def delete_selected_employee(self):
        if not self._write_enabled or not self._is_admin(): return
        employee = self._selected_employee()
        if employee is None: return
        reason = self._ask_reason(self, "Delete Employee", "Reason for deleting this employee:")
        if not reason: return
        confirm = QMessageBox.question(self, "Confirm Employee Deletion", f"Delete employee {employee.employee_code} — {employee.full_name}?\n\nEmployees with operational history cannot be hard-deleted.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return
        try:
            self._admin_service.delete_employee(employee.id, reason=reason)
            self.refresh_employees(); self._notify("Employee deleted.", "success")
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            QMessageBox.warning(self, "Delete Employee", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Delete Employee", f"Could not delete employee.\n\n{exc}")

    def reopen_period(self):
        if not self._write_enabled or not self._is_admin(): return
        year, month = self.year.value(), self.month.currentData()
        reason = self._ask_reason(self, "Re-open Registration Period", "Reason for reopening this closed period:")
        if not reason: return
        confirm = QMessageBox.question(self, "Confirm Period Re-open", f"Re-open the {month:02d}/{year} registration period?\n\nRegistrations keep their workflow status; DRAFT registrations become editable again when the period is OPEN.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return
        try:
            self._admin_service.reopen_period(year, month, reason=reason)
            self.refresh_period(); self._notify("Registration period reopened.", "success")
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            QMessageBox.warning(self, "Re-open Registration Period", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Re-open Registration Period", f"Could not reopen period.\n\n{exc}")

    def delete_selected_registration(self):
        if not self._write_enabled or not self._is_admin(): return
        registration = self._selected_registration()
        if registration is None: return
        reason = self._ask_reason(self, "Delete Registration", "Reason for deleting this registration:")
        if not reason: return
        confirm = QMessageBox.question(self, "Confirm Registration Deletion", f"Delete registration #{registration.id}?\n\nThe registration blocks will also be removed, but audit history is retained.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return
        try:
            self._admin_service.delete_registration(registration.id, reason=reason)
            self.refresh_period(); self._notify("Registration deleted.", "success")
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            QMessageBox.warning(self, "Delete Registration", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Delete Registration", f"Could not delete registration.\n\n{exc}")

    def _notify(self, message, level="info"):
        if self._notification_service is not None: self._notification_service.notify(message, level)
