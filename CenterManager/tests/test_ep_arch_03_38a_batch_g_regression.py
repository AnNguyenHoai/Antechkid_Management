"""Regression contract: Batch G must track services migrated after its baseline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def test_batch_g_legacy_contract_does_not_stale_mark_migrated_services():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in (
        "expense_service.py",
        "expense_timeline_service.py",
    ):
        row_start = source.index(f"`{service_name}`")
        row = source[row_start : source.index("\n", row_start)]
        assert "| PASS |" in row, row
