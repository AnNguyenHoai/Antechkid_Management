"""EP-ARCH-03.37 — post-merge architecture contract for Session/Timeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "architecture" / "EP-ARCH-03_SERVICE_INVENTORY.md"


def _row(source: str, service_name: str) -> str:
    start = source.index(f"`{service_name}`")
    return source[start : source.index("\n", start)]


def test_session_and_timeline_are_not_stale_legacy_entries():
    source = INVENTORY.read_text(encoding="utf-8")
    for service_name in ("session_service.py", "timeline_service.py"):
        assert "| PASS |" in _row(source, service_name)
