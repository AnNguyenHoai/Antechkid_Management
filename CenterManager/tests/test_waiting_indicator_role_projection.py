from pathlib import Path


SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")


def test_indicator_projects_writer_or_current_owner_not_waiting_queue():
    assert 'if self._transaction.is_editing:' in SOURCE
    assert 'self.waiting_indicator.setText("✏️ You are editing")' in SOURCE
    assert 'elif is_locked:' in SOURCE
    assert 'self.waiting_indicator.setText(f"🔒 {owner_text} is editing")' in SOURCE
    assert 'self.waiting_indicator.setText("● No active editor")' in SOURCE
    assert '⚠️ Waiting:' not in SOURCE


def test_finish_refreshes_owner_projection_without_queue_cleanup():
    finish_index = SOURCE.index("success = self._transaction.finish_editing(")
    refresh_index = SOURCE.index("self._update_waiting_status()", finish_index)

    assert refresh_index > finish_index
    assert "_snapshot_waiting_requests" not in SOURCE
