"""Capability-aware facade for the Employee Workspace shell.

The legacy shell owns the page lifecycle and collaboration integration. This
facade keeps that behavior intact while translating the global collaboration
WRITE state into operation-specific UI write permissions.
"""
from __future__ import annotations

from .employee_workspace_shell import (
    EmployeeWorkspaceShell as _EmployeeWorkspaceShell,
    LazyEmployeeProfileDialog as _LazyEmployeeProfileDialog,
)
from .employee_workspace_capabilities import EmployeeWorkspaceCapabilities
from .employee_workspace_write_policy import EmployeeWorkspaceWritePolicy


class CapabilityAwareLazyEmployeeProfileDialog(_LazyEmployeeProfileDialog):
    """Employee profile dialog whose operational actions use explicit capabilities."""

    def __init__(
        self,
        *args,
        workspace_write_enabled=False,
        capabilities: EmployeeWorkspaceCapabilities,
        **kwargs,
    ):
        self._workspace_write_enabled = bool(workspace_write_enabled)
        self._workspace_capabilities = capabilities
        is_self = bool(kwargs.get("self_mode", False))
        kwargs["editable"] = self._workspace_write_enabled and (
            capabilities.employee_update_self if is_self else capabilities.employee_update_all
        )
        super().__init__(*args, **kwargs)
        self.apply_operation_write_policy(
            self._workspace_write_enabled, self._workspace_capabilities
        )

    def apply_operation_write_policy(
        self,
        workspace_write_enabled: bool,
        capabilities: EmployeeWorkspaceCapabilities,
    ):
        self._workspace_write_enabled = bool(workspace_write_enabled)
        self._workspace_capabilities = capabilities
        self.editable = self._workspace_write_enabled and (
            capabilities.employee_update_self
            if self.self_mode
            else capabilities.employee_update_all
        )
        super()._apply_edit_state()
        if self._schedule_widget is not None:
            self._schedule_widget.set_editable(
                self._workspace_write_enabled
                and capabilities.schedule_manage
                and not self.self_mode
            )
        if self._working_time_widget is not None:
            self._working_time_widget.set_editable(
                self._workspace_write_enabled
                and (
                    capabilities.attendance_create_self
                    if self.self_mode
                    else capabilities.attendance_manage
                )
            )

    def _ensure_schedule_widget(self):
        super()._ensure_schedule_widget()
        if self._schedule_widget is not None:
            self._schedule_widget.set_editable(
                self._workspace_write_enabled
                and self._workspace_capabilities.schedule_manage
                and not self.self_mode
            )

    def _ensure_working_time_widget(self):
        super()._ensure_working_time_widget()
        if self._working_time_widget is not None:
            self._working_time_widget.set_editable(
                self._workspace_write_enabled
                and (
                    self._workspace_capabilities.attendance_create_self
                    if self.self_mode
                    else self._workspace_capabilities.attendance_manage
                )
            )


class CapabilityAwareEmployeeWorkspaceShell(_EmployeeWorkspaceShell):
    """Employee Workspace shell with explicit operation-level write gating."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._operation_write_policy = EmployeeWorkspaceWritePolicy.resolve(
            self.capabilities, self._write_enabled
        )
        self._apply_operation_write_policy()

    def _refresh_operation_write_policy(self):
        self._operation_write_policy = EmployeeWorkspaceWritePolicy.resolve(
            self.capabilities, self._write_enabled
        )

    def _apply_operation_write_policy(self):
        policy = self._operation_write_policy
        if self.list_page is not None:
            self.list_page.set_write_enabled(policy.employee_profile_all)
        if self.registration_review_page is not None:
            self.registration_review_page.set_write_enabled(policy.registration_manage)
        if self.registration_detail_page is not None:
            self.registration_detail_page.set_write_enabled(policy.registration_manage)
        if self.management_self_registration is not None and hasattr(
            self.management_self_registration, "set_editable"
        ):
            self.management_self_registration.set_editable(policy.registration_self)
        if self.self_page is not None:
            self.self_page.set_write_enabled(policy.employee_profile_self)
        if self._attendance_widget is not None:
            self._attendance_widget.set_editable(policy.working_time_create_self)
        if self.registration_page is not None and hasattr(
            self.registration_page, "set_editable"
        ):
            self.registration_page.set_editable(policy.registration_self)
        if self.profile_page is not None and hasattr(
            self.profile_page, "apply_operation_write_policy"
        ):
            self.profile_page.apply_operation_write_policy(
                self._write_enabled, self.capabilities
            )

    def set_write_enabled(self, enabled):
        """Apply collaboration WRITE as a gate, never as an authorization grant."""
        self._write_enabled = bool(enabled)
        self._refresh_operation_write_policy()
        self._apply_operation_write_policy()

    def _ensure_management_list_page(self):
        super()._ensure_management_list_page()
        self._apply_operation_write_policy()

    def _ensure_registration_review_page(self):
        super()._ensure_registration_review_page()
        self._apply_operation_write_policy()

    def _ensure_management_self_registration(self):
        super()._ensure_management_self_registration()
        self._apply_operation_write_policy()

    def _ensure_registration_page(self):
        super()._ensure_registration_page()
        self._apply_operation_write_policy()

    def _ensure_attendance_page(self):
        super()._ensure_attendance_page()
        self._apply_operation_write_policy()

    def open_employee_profile(self, employee):
        if self.profile_page is not None:
            self.stack.removeWidget(self.profile_page)
            self.profile_page.deleteLater()
        self.profile_page = CapabilityAwareLazyEmployeeProfileDialog(
            self._es,
            self._ds,
            self._schedule_service,
            self._working_time_service,
            employee,
            self,
            self_mode=False,
            editable=self._operation_write_policy.employee_profile_all,
            embedded=True,
            workspace_write_enabled=self._write_enabled,
            capabilities=self.capabilities,
        )
        if self.list_page is not None:
            self.profile_page.profile_saved.connect(self.list_page.refresh)
        self.profile_page.back_requested.connect(self._close_employee_profile)
        self.stack.addWidget(self.profile_page)
        self.stack.setCurrentWidget(self.profile_page)
        self.header.set_context(
            "Employee Workspace", f"Employee Profile • {employee.employee_code}"
        )
