"""EP-ARCH-03.35 — Legacy Service Migration Batch A contract tests.

Batch A promotes already-provider-backed legacy services into the strict
service-boundary inventory without changing their business behavior.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY = PROJECT_ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

BATCH_A_PASS_SERVICES = {
    "assessment_service.py",
    "attendance_service.py",
}


def test_batch_a_services_are_explicitly_promoted():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in BATCH_A_PASS_SERVICES:
        row_start = source.index(f"`{service_name}`")
        row = source[row_start:source.index("\n", row_start)]
        assert "| PASS |" in row, row
        assert "EP-ARCH-03.35" not in row, row


def test_batch_a_inventory_records_provider_backed_state():
    source = INVENTORY.read_text(encoding="utf-8")
    assert "AssessmentService" in source
    assert "AttendanceService" in source
    assert "RepositoryProvider" in source
