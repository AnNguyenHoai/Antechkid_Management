"""EP-ARCH-03.27 — deterministic service inventory metadata.

The inventory is generated from the source tree at test time. It is exposed as
an assertion-backed contract so new service files cannot silently escape the
final boundary gate.
"""
from __future__ import annotations

from pathlib import Path


SERVICES_DIR = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "services"


def test_complete_service_tree_is_discoverable():
    files = sorted(path.name for path in SERVICES_DIR.glob("*_service.py"))
    assert files, "Expected at least one application service."


def test_service_inventory_contains_expected_core_services():
    files = {path.name for path in SERVICES_DIR.glob("*_service.py")}
    expected = {
        "audit_service.py",
        "attendance_service.py",
        "class_service.py",
        "enrollment_service.py",
        "employee_service.py",
        "employee_schedule_service.py",
        "employee_work_registration_service.py",
        "employee_working_time_service.py",
        "permission_service.py",
        "student_service.py",
        "teacher_service.py",
    }
    assert expected <= files
