# -*- coding: utf-8 -*-
"""Employee workspace: capability-aware management and self-service UI."""
from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QLabel,
    QFormLayout, QMessageBox, QPushButton
)

from centermanager.core.current_user import get_current_user
from centermanager.services.employee_service import EmployeeServiceError
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from .employee_list_page import EmployeeListPage, EmployeeProfileDialog
from .employee_workspace_capabilities import EmployeeWorkspaceCapabilities

logger = logging.getLogger(__name__)


class LazyEmployeeProfileDialog(EmployeeProfileDialog):
    """Employee profile that loads operational tabs only when selected."""

    def __init__(self, *args, **kwargs):
        self._schedule_widget = None
        self._working_time_widget = None
        super().__init__(*args, **kwargs)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(self.tabs.currentIndex())

    def _build_schedule_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        title = QLabel("Expected working schedule")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        hint = QLabel("Weekly rules and date-specific exceptions.")
        hint.setStyleSheet("color: #68737d;")
        layout.addWidget(title)
        layout.addWidget(hint)
        placeholder = QLabel("Select the Schedule tab to load this employee's schedule.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)
        self._schedule_placeholder = placeholder
        self.tabs.addTab(page, "Schedule")

    def _build_working_time_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        title = QLabel("Actual working time")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        hint = QLabel("Recorded attendance and approved working-time entries.")
        hint.setStyleSheet("color: #68737d;")
        layout.addWidget(title)
        layout.addWidget(hint)
        placeholder = QLabel("Select the Attendance tab to load working-time records.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(placeholder, 1)
        self._working_time_placeholder = placeholder
        self.tabs.addTab(page, "Attendance")

    def _load(self):
        """Load identity/profile/document data without touching operational tabs."""
        e = self.employee
        self.header.setText(e.full_name or "Employee")
        self.subheader.setText(
            f"{e.employee_code or '-'}  •  {e.position or 'Position not set'}  •  "
            f"{e.department or 'Department not set'}"
        )
        self.status_badge.setText((e.employment_status or "UNKNOWN").replace("_", " "))
        self.code.setText(e.employee_code or "-")
        self.name.setText(e.full_name or "")
        if e.date_of_birth:
            self.dob.setDate(QDate(e.date_of_birth.year, e.date_of_birth.month, e.date_of_birth.day))
        else:
            self.dob.setDate(QDate(2000, 1, 1))
        self.gender.setText(e.gender or "")
        self.phone.setText(e.phone or "")
        self.email.setText(e.email or "")
        self.address.setPlainText(e.address or "")
        self.department.setText(e.department or "")
        self.position.setText(e.position or "")
        self.status.setCurrentText(e.employment_status or "ACTIVE")
        if e.hire_date:
            self.hire.setDate(QDate(e.hire_date.year, e.hire_date.month, e.hire_date.day))
        else:
            self.hire.setDate(QDate.currentDate())
        self._apply_edit_state()
        self._load_documents()

    def _on_tab_changed(self, index):
        tab_text = self.tabs.tabText(index)
        if tab_text == "Schedule":
            self._ensure_schedule_widget()
        elif tab_text == "Attendance":
            self._ensure_working_time_widget()

    def _ensure_schedule_widget(self):
        if self._schedule_widget is not None:
            return
        try:
            from centermanager.ui.employee_workspace.employee_schedule_widget import EmployeeScheduleWidget
            self._schedule_widget = EmployeeScheduleWidget(
                self.ss,
                self.employee,
                editable=self.editable and not self.self_mode,
                parent=self.tabs.widget(self.tabs.indexOf(self._schedule_placeholder)) if self._schedule_placeholder else self,
            )
            layout = self._schedule_placeholder.parentWidget().layout()
            layout.replaceWidget(self._schedule_placeholder, self._schedule_widget)
            self._schedule_placeholder.deleteLater()
            self._schedule_placeholder = None
        except Exception as exc:
            logger.exception("Failed to lazy-load employee schedule: employee_id=%s", self.employee.id)
            if self._schedule_placeholder is not None:
                self._schedule_placeholder.setText(f"Could not load schedule.\n\n{exc}")

    def _ensure_working_time_widget(self):
        if self._working_time_widget is not None:
            return
        try:
            from centermanager.ui.employee_workspace.employee_working_time_widget import EmployeeWorkingTimeWidget
            page = self.tabs.widget(self.tabs.indexOf(self._working_time_placeholder)) if self._working_time_placeholder else self
            self._working_time_widget = EmployeeWorkingTimeWidget(
                self.wts,
                self.employee,
                editable=self.editable and not self.self_mode,
                management=not self.self_mode,
                parent=page,
            )
            layout = self._working_time_placeholder.parentWidget().layout()
            layout.replaceWidget(self._working_time_placeholder, self._working_time_widget)
            self._working_time_placeholder.deleteLater()
            self._working_time_placeholder = None
        except Exception as exc:
            logger.exception("Failed to lazy-load employee working time: employee_id=%s", self.employee.id)
            if self._working_time_placeholder is not None:
                self._working_time_placeholder.setText(f"Could not load working time.\n\n{exc}")

    def _apply_edit_state(self):
        super()._apply_edit_state()
        if self._schedule_widget is not None:
            self._schedule_widget.set_editable(self.editable and not self.self_mode)
        if self._working_time_widget is not None:
            self._working_time_widget.set_editable(self.editable and not self.self_mode)


class MyEmployeeProfilePage(QWidget):
    """Self-service profile page. Personal data is editable; employment data is read-only."""

    def __init__(self, employee_service, document_service, schedule_service, working_time_service, parent=None):
        super().__init__(parent)
        self._service = employee_service
        self._documents = document_service
        self._schedule_service = schedule_service
        self._working_time_service = working_time_service
        self._write_enabled = False
        self.employee = None
        self._setup()

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)
        self.title = QLabel("My Employee Profile")
        self.title.setStyleSheet("font-size: 24px; font-weight: 700;")
        root.addWidget(self.title)
        self.summary = QLabel("Select My Profile to load your employee profile.")
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
            for field in self.fields.values():
                field.setText("-")
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
        self.edit_btn.setEnabled(bool(self.employee) and self._write_enabled)

    def edit_profile(self):
        if not self.employee:
            return
        try:
            dialog = LazyEmployeeProfileDialog(
                self._service, self._documents, self._schedule_service, self._working_time_service,
                self.employee, self, self_mode=True, editable=self._write_enabled
            )
            if dialog.exec():
                self.refresh()
        except Exception as exc:
            logger.exception("Failed to open self-service employee profile")
            QMessageBox.critical(self, "My Profile", f"Could not open profile.\n\nReason: {exc}")


class MyEmployeeSchedulePage(QWidget):
    """Read-only schedule view for the authenticated employee."""

    def __init__(self, employee_service, schedule_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._ss = schedule_service
        self._widget = None
        self._setup()

    def _setup(self):
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(28, 24, 28, 24)
        self.title = QLabel("My Schedule")
        self.title.setStyleSheet("font-size:24px;font-weight:700;")
        self.root.addWidget(self.title)
        self.body = QLabel("Select Schedule to load your working schedule.")
        self.root.addWidget(self.body)
        self.root.addStretch()

    def refresh(self):
        try:
            employee = self._es.get_current_employee()
            if self._widget is None:
                from centermanager.ui.employee_workspace.employee_schedule_widget import EmployeeScheduleWidget
                self._widget = EmployeeScheduleWidget(self._ss, employee, editable=False, parent=self)
                self.root.replaceWidget(self.body, self._widget)
                self.body.deleteLater()
            else:
                self._widget.employee = employee
                self._widget.refresh()
        except Exception as exc:
            logger.exception("Failed to load self employee schedule")
            self.body.setText(f"Could not load schedule.\n\n{exc}")


class EmployeeWorkspaceShell(QWidget):
    """Capability-aware Employee Workspace with lazy operational page loading."""

    go_home = Signal()

    def __init__(self, employee_service, document_service, schedule_service, working_time_service, work_registration_service, permission_service, parent=None):
        super().__init__(parent)
        self._es = employee_service
        self._ds = document_service
        self._schedule_service = schedule_service
        self._working_time_service = working_time_service
        self._work_registration_service = work_registration_service
        self._ps = permission_service
        self._write_enabled = False
        self.registration_detail_page = None
        self.list_page = None
        self.registration_review_page = None
        self.management_self_registration = None
        self.profile_page = None
        self.self_page = None
        self.attendance_page = None
        self._attendance_widget = None
        self.registration_page = None
        self.schedule_page = None
        self.capabilities = EmployeeWorkspaceCapabilities.resolve(self._ps, get_current_user())
        self.management_mode = self.capabilities.management
        self._setup()

    def _can_view_all_registrations(self, user=None):
        return self.capabilities.registration_all if user is None or user == get_current_user() else self._ps.has_permission("work_registration.view.all", user)

    def _can_view_self_registration(self, user=None):
        return self.capabilities.registration_self if user is None or user == get_current_user() else bool(
            self._ps.has_any_permission(["work_registration.self", "working_time.registration.self"], user)
        )

    @staticmethod
    def _placeholder(text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _setup(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.header = WorkspaceHeader("Employee Workspace", "Employees" if self.management_mode else "My Profile")
        self.header.back_home_clicked.connect(self.go_home.emit)
        root.addWidget(self.header)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.nav = WorkspaceNavigation(
            "Employee Workspace",
            self.capabilities.management_nav_items() if self.management_mode else self.capabilities.self_nav_items(),
        )
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)
        self.stack = QStackedWidget()

        if self.management_mode:
            self._management_placeholders = {}
            for page_id, text in (
                ("employees", "Select Employees to load the employee list."),
                ("registrations", "Select Work Registrations to load registrations."),
                ("my_registration", "Select My Work Registration to load your registration."),
            ):
                placeholder = self._placeholder(text)
                self._management_placeholders[page_id] = placeholder
                self.stack.addWidget(placeholder)
        else:
            self._self_placeholders = {}
            self.self_page = MyEmployeeProfilePage(
                self._es, self._ds, self._schedule_service, self._working_time_service, self
            )
            self.self_page.set_write_enabled(self._write_enabled)
            self.stack.addWidget(self.self_page)
            self._self_placeholders["profile"] = self.self_page

            self.attendance_page = self._placeholder("Select Attendance to load your working time.")
            self._self_placeholders["attendance"] = self.attendance_page
            self.stack.addWidget(self.attendance_page)

            self.registration_page = self._placeholder("Select Work Registration to load your registration.")
            self._self_placeholders["registration"] = self.registration_page
            self.stack.addWidget(self.registration_page)

            self.schedule_page = MyEmployeeSchedulePage(self._es, self._schedule_service, self)
            self._self_placeholders["schedule"] = self.schedule_page
            self.stack.addWidget(self.schedule_page)

        body.addWidget(self.stack, 1)
        root.addLayout(body)

    def _ensure_management_list_page(self):
        if self.list_page is not None:
            return
        self.list_page = EmployeeListPage(
            self._es, self._ds, self._schedule_service, self._working_time_service, self._ps, parent=self
        )
        self.list_page.set_profile_opener(self.open_employee_profile)
        self.list_page.set_write_enabled(self._write_enabled)
        placeholder = self._management_placeholders["employees"]
        index = self.stack.indexOf(placeholder)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, self.list_page)

    def _ensure_registration_review_page(self):
        if self.registration_review_page is not None:
            return
        if not self.capabilities.registration_all:
            return
        from centermanager.ui.employee_workspace.employee_work_registration_review_page import EmployeeWorkRegistrationReviewPage
        self.registration_review_page = EmployeeWorkRegistrationReviewPage(
            self._es, self._work_registration_service, parent=self
        )
        self.registration_review_page.detail_requested.connect(self.open_registration_detail)
        self.registration_review_page.set_write_enabled(self._write_enabled)
        placeholder = self._management_placeholders["registrations"]
        index = self.stack.indexOf(placeholder)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, self.registration_review_page)

    def _ensure_management_self_registration(self):
        if self.management_self_registration is not None and not isinstance(self.management_self_registration, QLabel):
            return
        if not self.capabilities.registration_self:
            return
        try:
            employee = self._es.get_current_employee()
        except Exception:
            logger.exception("Failed to resolve management user's employee identity")
            return
        from centermanager.ui.employee_workspace.employee_work_registration_widget import EmployeeWorkRegistrationWidget
        self.management_self_registration = EmployeeWorkRegistrationWidget(
            self._work_registration_service, employee, editable=self._write_enabled, parent=self
        )
        placeholder = self._management_placeholders["my_registration"]
        index = self.stack.indexOf(placeholder)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, self.management_self_registration)

    def _ensure_registration_page(self):
        if self.registration_page is not None and not isinstance(self.registration_page, QLabel):
            return
        if not self.capabilities.registration_self:
            return
        try:
            employee = self._es.get_current_employee()
        except Exception:
            logger.exception("Failed to resolve current employee for work registration")
            return
        from centermanager.ui.employee_workspace.employee_work_registration_widget import EmployeeWorkRegistrationWidget
        self.registration_page = EmployeeWorkRegistrationWidget(
            self._work_registration_service, employee, editable=self._write_enabled, parent=self
        )
        placeholder = self._self_placeholders["registration"]
        index = self.stack.indexOf(placeholder)
        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(index, self.registration_page)

    def _ensure_attendance_page(self):
        if self._attendance_widget is not None:
            return
        if not self.capabilities.attendance_self:
            return
        try:
            from centermanager.ui.employee_workspace.employee_working_time_widget import EmployeeWorkingTimeWidget
            employee = self._es.get_current_employee()
            widget = EmployeeWorkingTimeWidget(
                self._working_time_service, employee, editable=self._write_enabled, management=False, parent=self
            )
            self._attendance_widget = widget
            placeholder = self._self_placeholders["attendance"]
            index = self.stack.indexOf(placeholder)
            self.stack.removeWidget(placeholder)
            placeholder.deleteLater()
            self.stack.insertWidget(index, widget)
            self.attendance_page = widget
        except Exception as exc:
            logger.exception("Failed to lazy-load self attendance")
            self.attendance_page.setText(f"Could not load attendance.\n\n{exc}")

    def open_employee_profile(self, employee):
        if self.profile_page is not None:
            self.stack.removeWidget(self.profile_page)
            self.profile_page.deleteLater()
        self.profile_page = LazyEmployeeProfileDialog(
            self._es, self._ds, self._schedule_service, self._working_time_service,
            employee, self, self_mode=False, editable=self._write_enabled, embedded=True
        )
        self.profile_page.profile_saved.connect(self.list_page.refresh)
        self.profile_page.back_requested.connect(self._close_employee_profile)
        self.stack.addWidget(self.profile_page)
        self.stack.setCurrentWidget(self.profile_page)
        self.header.set_context("Employee Workspace", f"Employee Profile • {employee.employee_code}")

    def _close_employee_profile(self):
        if self.profile_page is not None:
            self.stack.setCurrentWidget(self.list_page)
            self.profile_page.deleteLater()
            self.profile_page = None
        self.header.set_context("Employee Workspace", "Employees")
        self.nav.set_active_page("employees")
        self.list_page.refresh()

    def open_registration_detail(self, registration):
        """Open a selected monthly registration in the dedicated manager detail page."""
        if not self.capabilities.registration_all:
            logger.warning("Blocked registration detail navigation without all-scope capability")
            return
        self._ensure_registration_review_page()
        if self.registration_detail_page is not None:
            self.stack.removeWidget(self.registration_detail_page)
            self.registration_detail_page.deleteLater()
            self.registration_detail_page = None
        from centermanager.ui.employee_workspace.employee_work_registration_detail_page import EmployeeWorkRegistrationDetailPage
        self.registration_detail_page = EmployeeWorkRegistrationDetailPage(
            self._work_registration_service, registration, parent=self
        )
        self.registration_detail_page.set_write_enabled(self._write_enabled)
        self.stack.addWidget(self.registration_detail_page)
        self.stack.setCurrentWidget(self.registration_detail_page)
        employee = getattr(registration, "employee", None)
        code = getattr(employee, "employee_code", "-")
        self.header.set_context("Employee Workspace", f"Registration Detail • {code}")

    def close_registration_detail(self):
        if self.registration_detail_page is not None:
            self.stack.removeWidget(self.registration_detail_page)
            self.registration_detail_page.deleteLater()
            self.registration_detail_page = None
        self._ensure_registration_review_page()
        if self.registration_review_page is not None:
            self.stack.setCurrentWidget(self.registration_review_page)
            self.nav.set_active_page("registrations")
            self.header.set_context("Employee Workspace", "Work Registrations")
            self.registration_review_page.refresh()

    def navigate_to(self, page_id):
        """Navigate only to capability-visible pages and lazy-load on first use."""
        if self.management_mode:
            if page_id == "employees" and self.capabilities.management:
                self._ensure_management_list_page()
                if self.list_page is not None:
                    self.stack.setCurrentWidget(self.list_page)
                    self.nav.set_active_page("employees")
                    self.header.set_context("Employee Workspace", "Employees")
                    self.list_page.refresh()
                return
            if page_id == "registrations" and self.capabilities.registration_all:
                self._ensure_registration_review_page()
                if self.registration_review_page is not None:
                    self.stack.setCurrentWidget(self.registration_review_page)
                    self.nav.set_active_page("registrations")
                    self.header.set_context("Employee Workspace", "Work Registrations")
                    self.registration_review_page.refresh()
                return
            if page_id == "my_registration" and self.capabilities.registration_self:
                self._ensure_management_self_registration()
                if self.management_self_registration is not None and not isinstance(self.management_self_registration, QLabel):
                    self.stack.setCurrentWidget(self.management_self_registration)
                    self.nav.set_active_page("my_registration")
                    self.header.set_context("Employee Workspace", "My Work Registration")
                    if hasattr(self.management_self_registration, "refresh"):
                        self.management_self_registration.refresh()
                return
            logger.warning("Blocked Employee Workspace navigation: page_id=%s", page_id)
            return

        if page_id == "attendance":
            if not self.capabilities.attendance_self:
                logger.warning("Blocked attendance navigation without working_time.view.self")
                return
            self._ensure_attendance_page()
            self.stack.setCurrentWidget(self.attendance_page)
            self.header.set_context("Employee Workspace", "Attendance")
            self.nav.set_active_page("attendance")
            if hasattr(self.attendance_page, "refresh"):
                self.attendance_page.refresh()
            return

        if page_id == "registration":
            if not self.capabilities.registration_self:
                logger.warning("Blocked registration navigation without self capability")
                return
            self._ensure_registration_page()
            if self.registration_page is not None and not isinstance(self.registration_page, QLabel):
                self.stack.setCurrentWidget(self.registration_page)
                self.header.set_context("Employee Workspace", "Work Registration")
                self.nav.set_active_page("registration")
                if hasattr(self.registration_page, "refresh"):
                    self.registration_page.refresh()
            return

        if page_id == "schedule":
            if not self.capabilities.schedule_self:
                logger.warning("Blocked schedule navigation without schedule.view.self")
                return
            self.stack.setCurrentWidget(self.schedule_page)
            self.header.set_context("Employee Workspace", "Schedule")
            self.nav.set_active_page("schedule")
            self.schedule_page.refresh()
            return

        if page_id == "profile":
            self.stack.setCurrentWidget(self.self_page)
            self.header.set_context("Employee Workspace", "My Profile")
            self.nav.set_active_page("profile")
            self.self_page.refresh()
            return

        logger.warning("Unknown Employee Workspace page: %s", page_id)

    def set_write_enabled(self, enabled):
        self._write_enabled = bool(enabled)
        if self.list_page is not None:
            self.list_page.set_write_enabled(self._write_enabled)
        if self.registration_review_page is not None:
            self.registration_review_page.set_write_enabled(self._write_enabled)
        if self.registration_detail_page is not None:
            self.registration_detail_page.set_write_enabled(self._write_enabled)
        if self.management_self_registration is not None and hasattr(self.management_self_registration, "set_editable"):
            self.management_self_registration.set_editable(self._write_enabled)
        if self.self_page is not None:
            self.self_page.set_write_enabled(self._write_enabled)
        if self._attendance_widget is not None:
            self._attendance_widget.set_editable(self._write_enabled)
        if self.registration_page is not None and hasattr(self.registration_page, "set_editable"):
            self.registration_page.set_editable(self._write_enabled)
        if self.profile_page is not None and hasattr(self.profile_page, "editable"):
            self.profile_page.editable = self._write_enabled
            self.profile_page._apply_edit_state()
