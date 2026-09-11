"""Regression guard for the RepositoryProvider migration.

The working-time service intentionally has no concrete repository symbols in
its module namespace. Fixtures must inject repository doubles through the
provider seam rather than monkeypatching removed concrete imports.
"""
from pathlib import Path


SERVICE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "services"
    / "employee_working_time_service.py"
)


def test_employee_working_time_service_does_not_expose_concrete_repository_symbols():
    source = SERVICE.read_text(encoding="utf-8")
    assert "EmployeeRepository" not in source
    assert "EmployeeWorkingTimeRepository" not in source
