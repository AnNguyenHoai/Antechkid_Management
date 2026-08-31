# -*- coding: utf-8 -*-
"""Employee workspace: management view for Admin/Manager and self-service view for employees."""
from __future__ import annotations

import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel,
    QTabWidget, QPushButton, QFormLayout, QMessageBox
)
from centermanager.core.current_user import get_current_user
from centermanager.services.employee_service import EmployeeServiceError, EmployeeAccessDeniedError
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from .employee_list_page import EmployeeListPage, EmployeeProfileDialog

logger = logging.getLogger(__name__)


class MyEmployeeProfilePage(QWidget):
    """Self-service profile page. Personal data is editable; employment data is read-only."""

    def __init__(self, employee_service, document_service, parent=None):
        super().__init__(parent)
        self._service = employee_service
        self._documents = document_service
        # WRITE mode is controlled by the application's global write guard.
        self._write_enabled = False
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        self.title = QLabel("My Employee Profile")
        self.title.setStyleSheet("font-size: 24px; font-weight: 700;")
        root.addWidget(self.title)

        self.summary = QLabel("-")
        self.summary.setStyleSheet("font-size: 14px;")
        root.addWidget(self.summary)

        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.fields = {}
        for key, label in [
            ("employee_code", "Employee Code"),
            ("full_name", "Full Name"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("department", "Department"),
            ("position", "Position"),
            ("employment_status", "Status"),
            ("hire_date", "Hire Date"),
        ]:
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.fields[key] = value
            form.addRow(f"{label}:", value)
        root.addLayout(form)

        self.cv_label = QLabel("CV: -")
        root.addWidget(self.cv_label)
        self.edit_btn = QPushButton("Edit My Profile")
        self.edit_btn.clicked.connect(self.edit_profile)
        root.addWidget(self.edit_btn)
        root.addStretch()

    def refresh(self):
        try:
            employee = self._service.get_current_employee()
            self.employee = employee
        except EmployeeServiceError as exc:
            logger.warning("Current account has no linked employee: %s", exc)
            self.employee = None
            self.summary.setText("No employee profile is linked to this account.")
            for field in self.fields.values(): field.setText("-")
            self.cv_label.setText("CV: -")
            self.edit_btn.setEnabled(False)
            return
        except Exception:
            logger.exception("Failed to load current employee profile")
            return

        self.title.setText(employee.full_name or "My Employee Profile")
        self.summary.setText(
            f"{employee.employee_code}  •  {employee.position or 'Position not set'}  •  "
            f"{employee.department or 'Department not set'}"
        )
        for key, field in self.fields.items():
            value = getattr(employee, key, None)
            field.setText(str(value) if value not in (None, "") else "-")
        try:
            docs = self._documents.list_documents(employee.id)
            cv = next((d for d in docs if d.document_type == "CV"), None)
            self.cv_label.setText(f"CV: {cv.original_filename}" if cv else "CV: Not uploaded")
        except Exception:
            logger.exception("Failed to load current employee documents")
            self.cv_label.setText("CV: Unable to load")
        self.edit_btn.setEnabled(self._write_enabled)

    def set_write_enabled(self, enabled: bool) -> None:
        """Apply the global WRITE lock to self-service profile editing."""
        self._write_enabled = bool(enabled)
        self.edit_btn.setEnabled(bool(getattr(self, "employee", None)) and self._write_enabled)

    def edit_profile(self):
        if not getattr(self, "employee", None):
            return
        try:
            dialog = EmployeeProfileDialog(
                self._service, self._documents, self.employee, self, self_mode=True,
                editable=self._write_enabled
            )
            if dialog.exec():
                self.refresh()
        except Exception as exc:
            logger.exception("Failed to open self-service employee profile")
            QMessageBox.critical(self, "My Profile", f"Could not open profile.\n\nReason: {exc}")


class EmployeeWorkspaceShell(QWidget):
    go_home = Signal()

    def __init__(self, employee_service, document_service, permission_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._ds = document_service
        self._ps = permission_service
        # Global WRITE mode is OFF until MainWindow explicitly grants it.
        self._write_enabled = False
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header = WorkspaceHeader("Employee Workspace", "My Profile")
        self.header.back_home_clicked.connect(self.go_home.emit)
        root.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        user = get_current_user()
        self.management_mode = self._es.can_view_all(user)

        if self.management_mode:
            self.nav = WorkspaceNavigation(
                "Employee Workspace",
                [{"id": "employees", "icon": "👥", "label": "Employees"}],
            )
            self.nav.page_selected.connect(self.navigate_to)
            body.addWidget(self.nav)
            self.stack = QStackedWidget()
            self.list_page = EmployeeListPage(self._es, self._ds, self._ps, parent=self)
            self.stack.addWidget(self.list_page)
            body.addWidget(self.stack, 1)
        else:
            self.nav = WorkspaceNavigation(
                "Employee Workspace",
                [{"id": "profile", "icon": "👤", "label": "My Profile"},
                 {"id": "attendance", "icon": "🕒", "label": "Attendance"}],
            )
            self.nav.page_selected.connect(self.navigate_to)
            body.addWidget(self.nav)
            self.stack = QStackedWidget()
            self.self_page = MyEmployeeProfilePage(self._es, self._ds, self)
            self.self_page.set_write_enabled(self._write_enabled)
            self.stack.addWidget(self.self_page)
            attendance = QLabel(
                "Attendance / Working Time\n\n"
                "Working-time booking will be implemented in EMPLOYEE 1.4."
            )
            attendance.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.stack.addWidget(attendance)
            body.addWidget(self.stack, 1)

        root.addLayout(body)
        if not self.management_mode:
            self.self_page.refresh()

    def navigate_to(self, page_id):
        if self.management_mode:
            self.stack.setCurrentWidget(self.list_page)
            self.nav.set_active_page("employees")
            self.header.set_context("Employee Workspace", "Employees")
            self.list_page.refresh()
        else:
            if page_id == "attendance":
                self.stack.setCurrentIndex(1)
                self.header.set_context("Employee Workspace", "Attendance")
                self.nav.set_active_page("attendance")
            else:
                self.stack.setCurrentIndex(0)
                self.header.set_context("Employee Workspace", "My Profile")
                self.nav.set_active_page("profile")
                self.self_page.refresh()

    def set_write_enabled(self, enabled):
        self._write_enabled = bool(enabled)
        if self.management_mode:
            self.list_page.set_write_enabled(self._write_enabled)
        else:
            self.self_page.set_write_enabled(self._write_enabled)
