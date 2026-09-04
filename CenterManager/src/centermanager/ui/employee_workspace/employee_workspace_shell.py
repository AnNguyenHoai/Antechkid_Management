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

    def __init__(self, employee_service, document_service, schedule_service, working_time_service, parent=None):
        super().__init__(parent)
        self._service = employee_service
        self._documents = document_service
        self._schedule_service = schedule_service
        self._working_time_service = working_time_service
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
            ("employee_code", "Employee Code"), ("full_name", "Full Name"),
            ("phone", "Phone"), ("email", "Email"), ("department", "Department"),
            ("position", "Position"), ("employment_status", "Status"), ("hire_date", "Hire Date"),
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
        self._write_enabled = bool(enabled)
        self.edit_btn.setEnabled(bool(getattr(self, "employee", None)) and self._write_enabled)

    def edit_profile(self):
        if not getattr(self, "employee", None): return
        try:
            dialog = EmployeeProfileDialog(
                self._service, self._documents, self._schedule_service, self._working_time_service,
                self.employee, self, self_mode=True, editable=self._write_enabled
            )
            if dialog.exec(): self.refresh()
        except Exception as exc:
            logger.exception("Failed to open self-service employee profile")
            QMessageBox.critical(self, "My Profile", f"Could not open profile.\n\nReason: {exc}")


class MyEmployeeSchedulePage(QWidget):
    """Read-only schedule view for the authenticated employee."""
    def __init__(self, employee_service, schedule_service, parent=None):
        super().__init__(parent); self._es=employee_service; self._ss=schedule_service; self._widget=None; self._setup()
    def _setup(self):
        self.root=QVBoxLayout(self); self.root.setContentsMargins(28,24,28,24); self.title=QLabel("My Schedule"); self.title.setStyleSheet("font-size:24px;font-weight:700;"); self.root.addWidget(self.title); self.body=QLabel("Loading schedule…"); self.root.addWidget(self.body); self.root.addStretch()
    def refresh(self):
        try:
            employee=self._es.get_current_employee()
            if self._widget is None:
                from centermanager.ui.employee_workspace.employee_schedule_widget import EmployeeScheduleWidget
                self._widget=EmployeeScheduleWidget(self._ss, employee, editable=False, parent=self); self.root.replaceWidget(self.body, self._widget); self.body.deleteLater()
            else: self._widget.employee=employee; self._widget.refresh()
        except Exception as exc: self.body.setText(f"Could not load schedule.\n\n{exc}")


class EmployeeWorkspaceShell(QWidget):
    go_home = Signal()

    def __init__(self, employee_service, document_service, schedule_service, working_time_service, work_registration_service, permission_service, parent=None):
        super().__init__(parent)
        self._es = employee_service; self._ds = document_service; self._schedule_service = schedule_service
        self._working_time_service = working_time_service; self._work_registration_service = work_registration_service; self._ps = permission_service
        self._write_enabled = False
        self.registration_detail_page = None
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.header = WorkspaceHeader("Employee Workspace", "My Profile")
        self.header.back_home_clicked.connect(self.go_home.emit); root.addWidget(self.header)
        body = QHBoxLayout(); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(0)
        user = get_current_user(); self.management_mode = self._es.can_view_all(user)

        if self.management_mode:
            try:
                management_employee = self._es.get_current_employee(user)
            except EmployeeServiceError:
                management_employee = None
            except Exception:
                logger.exception("Failed to resolve management user's employee identity")
                management_employee = None

            nav_items = [
                {"id": "employees", "icon": "👥", "label": "Employees"},
                {"id": "registrations", "icon": "📝", "label": "Work Registrations"},
            ]
            if management_employee is not None:
                nav_items.append({"id": "my_registration", "icon": "👤", "label": "My Work Registration"})

            self.nav = WorkspaceNavigation("Employee Workspace", nav_items)
            self.nav.page_selected.connect(self.navigate_to); body.addWidget(self.nav)
            self.stack = QStackedWidget()
            self.list_page = EmployeeListPage(self._es, self._ds, self._schedule_service, self._working_time_service, self._ps, parent=self)
            self.profile_page = None; self.list_page.set_profile_opener(self.open_employee_profile); self.stack.addWidget(self.list_page)
            from centermanager.ui.employee_workspace.employee_work_registration_review_page import EmployeeWorkRegistrationReviewPage
            self.registration_review_page = EmployeeWorkRegistrationReviewPage(self._es, self._work_registration_service, parent=self)
            self.registration_review_page.detail_requested.connect(self.open_registration_detail)
            self.stack.addWidget(self.registration_review_page)
            if management_employee:
                from centermanager.ui.employee_workspace.employee_work_registration_widget import EmployeeWorkRegistrationWidget
                self.management_self_registration = EmployeeWorkRegistrationWidget(self._work_registration_service, management_employee, editable=self._write_enabled, parent=self); self.stack.addWidget(self.management_self_registration)
            else:
                self.management_self_registration = QLabel("No employee profile is linked to this account."); self.management_self_registration.setAlignment(Qt.AlignmentFlag.AlignCenter); self.stack.addWidget(self.management_self_registration)
            body.addWidget(self.stack, 1)
        else:
            self.nav = WorkspaceNavigation(
                "Employee Workspace",
                [{"id": "profile", "icon": "👤", "label": "My Profile"}, {"id": "attendance", "icon": "🕒", "label": "Attendance"},
                 {"id": "registration", "icon": "📝", "label": "Work Registration"}, {"id": "schedule", "icon": "📅", "label": "Schedule"}],
            )
            self.nav.page_selected.connect(self.navigate_to); body.addWidget(self.nav); self.stack = QStackedWidget()
            self.self_page = MyEmployeeProfilePage(self._es, self._ds, self._schedule_service, self); self.self_page.set_write_enabled(self._write_enabled); self.stack.addWidget(self.self_page)
            attendance = QLabel("Select Attendance to load your working time."); attendance.setAlignment(Qt.AlignmentFlag.AlignCenter); self.attendance_page = attendance; self._attendance_widget = None; self.stack.addWidget(attendance)
            from centermanager.ui.employee_workspace.employee_work_registration_widget import EmployeeWorkRegistrationWidget
            employee = None
            try: employee = self._es.get_current_employee()
            except Exception: pass
            self.registration_page = EmployeeWorkRegistrationWidget(self._work_registration_service, employee, editable=self._write_enabled, parent=self) if employee else QLabel("No employee profile is linked to this account.")
            self.stack.addWidget(self.registration_page); self.schedule_page = MyEmployeeSchedulePage(self._es, self._schedule_service, self); self.stack.addWidget(self.schedule_page); body.addWidget(self.stack, 1)
        root.addLayout(body)
        if not self.management_mode: self.self_page.refresh()

    def _ensure_attendance_page(self):
        if self._attendance_widget is not None: return
        try:
            from centermanager.ui.employee_workspace.employee_working_time_widget import EmployeeWorkingTimeWidget
            employee = self._es.get_current_employee(); widget = EmployeeWorkingTimeWidget(self._working_time_service, employee, editable=self._write_enabled, management=False, parent=self); self._attendance_widget = widget
            self.stack.removeWidget(self.attendance_page); self.attendance_page.deleteLater(); self.attendance_page = widget; self.stack.insertWidget(1, widget)
        except Exception as exc: self.attendance_page.setText(f"Could not load attendance.\n\n{exc}")

    def open_employee_profile(self, employee):
        if self.profile_page is not None: self.stack.removeWidget(self.profile_page); self.profile_page.deleteLater()
        self.profile_page = EmployeeProfileDialog(self._es, self._ds, self._schedule_service, self._working_time_service, employee, self, self_mode=False, editable=self._write_enabled, embedded=True)
        self.profile_page.profile_saved.connect(self.list_page.refresh); self.profile_page.back_requested.connect(self._close_employee_profile); self.stack.addWidget(self.profile_page); self.stack.setCurrentWidget(self.profile_page); self.header.set_context("Employee Workspace", f"Employee Profile • {employee.employee_code}")

    def _close_employee_profile(self):
        if self.profile_page is not None: self.stack.setCurrentWidget(self.list_page); self.profile_page.deleteLater(); self.profile_page = None
        self.header.set_context("Employee Workspace", "Employees"); self.nav.set_active_page("employees"); self.list_page.refresh()

    def open_registration_detail(self, registration):
        """Open a selected monthly registration in the dedicated manager detail page."""
        if self.registration_detail_page is not None:
            self.stack.removeWidget(self.registration_detail_page); self.registration_detail_page.deleteLater(); self.registration_detail_page = None
        from centermanager.ui.employee_workspace.employee_work_registration_detail_page import EmployeeWorkRegistrationDetailPage
        self.registration_detail_page = EmployeeWorkRegistrationDetailPage(self._work_registration_service, registration, parent=self)
        self.registration_detail_page.set_write_enabled(self._write_enabled)
        self.stack.addWidget(self.registration_detail_page); self.stack.setCurrentWidget(self.registration_detail_page)
        employee = getattr(registration, "employee", None); code = getattr(employee, "employee_code", "-")
        self.header.set_context("Employee Workspace", f"Registration Detail • {code}")

    def close_registration_detail(self):
        if self.registration_detail_page is not None:
            self.stack.removeWidget(self.registration_detail_page); self.registration_detail_page.deleteLater(); self.registration_detail_page = None
        self.stack.setCurrentWidget(self.registration_review_page); self.nav.set_active_page("registrations")
        self.header.set_context("Employee Workspace", "Work Registrations"); self.registration_review_page.refresh()

    def navigate_to(self, page_id):
        if self.management_mode:
            if page_id == "registrations":
                self.stack.setCurrentWidget(self.registration_review_page); self.nav.set_active_page("registrations"); self.header.set_context("Employee Workspace", "Work Registrations"); self.registration_review_page.refresh()
            elif page_id == "my_registration" and self.management_self_registration is not None:
                self.stack.setCurrentWidget(self.management_self_registration); self.nav.set_active_page("my_registration"); self.header.set_context("Employee Workspace", "My Work Registration")
                if hasattr(self.management_self_registration, "refresh"): self.management_self_registration.refresh()
            else:
                self.stack.setCurrentWidget(self.list_page); self.nav.set_active_page("employees"); self.header.set_context("Employee Workspace", "Employees"); self.list_page.refresh()
        else:
            if page_id == "attendance":
                self._ensure_attendance_page(); self.stack.setCurrentIndex(1); self.header.set_context("Employee Workspace", "Attendance"); self.nav.set_active_page("attendance")
            elif page_id == "registration":
                self.stack.setCurrentWidget(self.registration_page); self.header.set_context("Employee Workspace", "Work Registration"); self.nav.set_active_page("registration")
                if hasattr(self.registration_page, "refresh"): self.registration_page.refresh()
            elif page_id == "schedule":
                self.stack.setCurrentIndex(3); self.header.set_context("Employee Workspace", "Schedule"); self.nav.set_active_page("schedule"); self.schedule_page.refresh()
            else:
                self.stack.setCurrentIndex(0); self.header.set_context("Employee Workspace", "My Profile"); self.nav.set_active_page("profile"); self.self_page.refresh()

    def set_write_enabled(self, enabled):
        self._write_enabled = bool(enabled)
        if self.management_mode:
            self.list_page.set_write_enabled(self._write_enabled)
            self.registration_review_page.set_write_enabled(self._write_enabled)
            if self.registration_detail_page is not None: self.registration_detail_page.set_write_enabled(self._write_enabled)
            if hasattr(self.management_self_registration, "set_editable"): self.management_self_registration.set_editable(self._write_enabled)
        else:
            self.self_page.set_write_enabled(self._write_enabled)
            if self._attendance_widget is not None: self._attendance_widget.set_editable(self._write_enabled)
            if hasattr(self.registration_page, "set_editable"): self.registration_page.set_editable(self._write_enabled)
