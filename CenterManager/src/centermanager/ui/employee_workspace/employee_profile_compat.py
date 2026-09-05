"""Compatibility patch for the lazy employee profile loader.

The lazy profile subclass in ``employee_workspace_shell`` overrides ``_load``.
Its previous implementation imported ``QDate`` inside a conditional branch,
which made QDate a function-local variable and raised UnboundLocalError when
an employee had no date of birth. Reusing the base loader keeps the profile
fields identical while retaining the subclass's lazy operational-tab behavior:
the base loader only refreshes operational widgets when those attributes exist,
which they do not before the lazy tabs are materialized.
"""

from .employee_list_page import EmployeeProfileDialog
from .employee_workspace_shell import LazyEmployeeProfileDialog


def apply_compatibility_fix() -> None:
    """Bind the lazy profile loader to the safe base implementation."""
    LazyEmployeeProfileDialog._load = EmployeeProfileDialog._load
