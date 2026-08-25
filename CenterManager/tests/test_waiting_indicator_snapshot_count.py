from pathlib import Path


SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")


def test_poller_preserves_numeric_waiting_count_even_without_request_metadata():
    assert "self._snapshot_waiting_count = snapshot_count" in SOURCE
    assert 'queue.get("length", len(snapshot_requests))' in SOURCE


def test_writer_uses_snapshot_count_when_request_details_have_not_converged():
    assert "snapshot_count = max(0, int(getattr(self, \"_snapshot_waiting_count\", 0) or 0))" in SOURCE
    assert "waiting_count = max(request_count, snapshot_count)" in SOURCE


def test_legacy_no_waiting_label_is_not_used():
    assert '● No waiting' not in SOURCE
