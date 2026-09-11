"""Operation-level write policy for Employee Workspace UI.

The collaboration write lock is a separate gate from authorization.  This
module combines the two without turning a generic WRITE state into permission
to edit every employee operation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .employee_workspace_capabilities import EmployeeWorkspaceCapabilities


@dataclass(frozen=True)
class EmployeeWorkspaceWritePolicy:
    """Effective write capabilities while the collaboration lock is held."""

    employee_profile_self: bool
    employee_profile_all: bool
    schedule_manage: bool
    working_time_create_self: bool
    working_time_manage: bool
    registration_self: bool
    registration_manage: bool

    @classmethod
    def resolve(
        cls,
        capabilities: EmployeeWorkspaceCapabilities,
        write_lock_held: bool,
    ) -> "EmployeeWorkspaceWritePolicy":
        """Combine the global collaboration write gate with explicit capabilities."""
        gate = bool(write_lock_held)
        return cls(
            employee_profile_self=gate and capabilities.employee_update_self,
            employee_profile_all=gate and capabilities.employee_update_all,
            schedule_manage=gate and capabilities.schedule_manage,
            working_time_create_self=gate and capabilities.attendance_create_self,
            working_time_manage=gate and capabilities.attendance_manage,
            registration_self=gate and capabilities.registration_self,
            registration_manage=gate and capabilities.registration_manage,
        )
