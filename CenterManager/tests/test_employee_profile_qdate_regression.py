from centermanager.ui.employee_workspace.employee_list_page import EmployeeProfileDialog
from centermanager.ui.employee_workspace.employee_workspace_shell import LazyEmployeeProfileDialog


def test_lazy_employee_profile_uses_safe_base_loader():
    """A missing DOB must not execute the old branch-local QDate import path."""
    assert LazyEmployeeProfileDialog._load is EmployeeProfileDialog._load
