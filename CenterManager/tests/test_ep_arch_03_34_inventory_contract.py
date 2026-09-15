"""EP-ARCH-03.34 — canonical inventory contract checks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

EXPECTED_PASS_SERVICES = {
    "employee_admin_management_service.py",
    "employee_schedule_service.py",
    "employee_service.py",
    "employee_work_registration_service.py",
    "employee_working_time_service.py",
    "home_dashboard_service.py",
    "outstanding_service.py",
    "parent_service.py",
    "permission_service.py",
    "session_note_service.py",
    "session_report_service.py",
}


def test_inventory_exists_and_declares_baseline():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "EP-ARCH-03 — Service Boundary Inventory" in source
    assert "a23ad673cdaea144244456b782371baf40914756" in source


def test_inventory_marks_known_clean_services_as_pass():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in EXPECTED_PASS_SERVICES:
        row_start = source.index(f"`{service_name}`")
        row = source[row_start:source.index("\n", row_start)]
        assert "| PASS |" in row, row


def test_inventory_preserves_legacy_backlog():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "| LEGACY |" in source
    assert "EP-ARCH-03.35" in source
    assert "EP-ARCH-03.36" in source
    assert "EP-ARCH-03.37" in source
    assert "EP-ARCH-03.38" in source
    assert "EP-ARCH-03.39" in source


def test_inventory_has_no_violation_status_at_baseline():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "| VIOLATION |" not in source
