from pathlib import Path


SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")


def test_writer_role_uses_local_editing_state_not_remote_lock_session():
    assert "if self._transaction.is_editing:" in SOURCE
    assert 'if is_locked and lock_session == current_session:' not in SOURCE


def test_writer_displays_editing_state_not_waiting_count():
    assert 'self.waiting_indicator.setText("✏️ You are editing")' in SOURCE
    assert '⚠️ Waiting:' not in SOURCE


def test_non_writer_displays_current_write_owner():
    assert 'elif is_locked:' in SOURCE
    assert 'self.waiting_indicator.setText(f"🔒 {owner_text} is editing")' in SOURCE


def test_write_grant_repaints_indicator():
    granted = SOURCE.index("def _on_write_granted")
    refresh = SOURCE.index("self._update_waiting_status()", granted)
    assert refresh > granted
