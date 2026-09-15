"""EP-ARCH-03.35 — Legacy Service Migration Batch B contract tests.

Batch B promotes services that are already provider-backed into the strict
service-boundary inventory. The tests intentionally verify both the inventory
classification and the source-level RepositoryProvider contract.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"
INVENTORY = PROJECT_ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

BATCH_B_SERVICES = {
    "audit_service.py": "AuditService",
    "class_service.py": "ClassService",
}


def test_batch_b_services_are_explicitly_promoted():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name, class_name in BATCH_B_SERVICES.items():
        row_start = source.index(f"`{service_name}`")
        row = source[row_start:source.index("\n", row_start)]
        assert "| PASS |" in row, row
        assert "EP-ARCH-03.35" not in row, row
        assert class_name in source


def test_batch_b_services_use_repository_provider_contract():
    for service_name in BATCH_B_SERVICES:
        source = (SERVICES_DIR / service_name).read_text(encoding="utf-8")
        assert "RepositoryProvider" in source
        assert "create_default_repository_provider" in source or "SqlAlchemyRepositoryProvider" in source
        assert "session.query(" not in source


def test_batch_b_inventory_documents_the_boundary():
    source = INVENTORY.read_text(encoding="utf-8")
    batch_section = source[source.index("## EP-ARCH-03.35 Batch B"):]
    assert "AuditService" in batch_section
    assert "ClassService" in batch_section
    assert "RepositoryProvider" in batch_section
