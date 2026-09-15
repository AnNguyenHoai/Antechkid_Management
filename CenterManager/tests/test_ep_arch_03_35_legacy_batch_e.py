"""EP-ARCH-03.35 — Legacy Service Migration Batch E contract tests."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES_DIR = PROJECT_ROOT / "src" / "centermanager" / "services"
INVENTORY = PROJECT_ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"

BATCH_E_SERVICES = {
    "class_timeline_service.py": "ClassTimelineService",
}


def test_batch_e_services_are_explicitly_promoted():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name, class_name in BATCH_E_SERVICES.items():
        row_start = source.index(f"`{service_name}`")
        row = source[row_start:source.index("\n", row_start)]
        assert "| PASS |" in row, row
        assert "EP-ARCH-03.35" not in row, row
        assert class_name in source


def test_batch_e_services_use_repository_provider_contract():
    for service_name in BATCH_E_SERVICES:
        source = (SERVICES_DIR / service_name).read_text(encoding="utf-8")
        assert "RepositoryProvider" in source
        assert "class_timeline(" in source
        assert "repo.add(" in source
        assert "repo.refresh(" in source
        assert "session.query(" not in source
        assert "session.add(" not in source
        assert "session.delete(" not in source
        assert "session.refresh(" not in source


def test_batch_e_inventory_documents_the_boundary():
    source = INVENTORY.read_text(encoding="utf-8")
    batch_section = source[source.index("## EP-ARCH-03.35 Batch E"):]
    assert "ClassTimelineService" in batch_section
    assert "RepositoryProvider.class_timeline" in batch_section
    assert "repository-owned" in batch_section
