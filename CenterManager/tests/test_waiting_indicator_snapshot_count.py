from pathlib import Path


SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")


def test_waiting_queue_snapshot_is_not_projected_into_ui():
    assert "_snapshot_waiting_count" not in SOURCE
    assert "_snapshot_waiting_requests" not in SOURCE
    assert "⚠️ Waiting:" not in SOURCE


def test_legacy_no_waiting_label_is_not_used():
    assert '● No waiting' not in SOURCE
