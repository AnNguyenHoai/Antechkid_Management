from pathlib import Path


SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")


def test_writer_role_uses_transaction_editing_state():
    assert "if self._transaction.is_editing:" in SOURCE
    assert 'self.waiting_indicator.setText(f"⚠️ Waiting: {waiting_count}")' in SOURCE


def test_writer_default_is_waiting_zero():
    assert 'self.waiting_indicator = QLabel("⚠️ Waiting: 0")' in SOURCE
    assert 'self.waiting_indicator.setText("⚠️ Waiting: 0")' in SOURCE


def test_non_writer_sees_lock_owner():
    assert 'elif is_locked:' in SOURCE
    assert 'self.waiting_indicator.setText(f"🔒 {owner_text} is editing")' in SOURCE


def test_write_grant_repaints_indicator():
    granted = SOURCE.index("def _on_write_granted")
    assert SOURCE.index("self._update_waiting_status()", granted) > granted
