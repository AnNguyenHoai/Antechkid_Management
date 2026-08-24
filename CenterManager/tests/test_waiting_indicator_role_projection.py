from pathlib import Path


def test_waiting_indicator_is_role_specific():
    source = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")

    assert 'if is_locked and lock_session == current_session:' in source
    assert 'self.waiting_indicator.setText(f"⚠️ Waiting: {waiting_count}")' in source
    assert 'elif is_locked and lock_session != current_session:' in source
    assert 'self.waiting_indicator.setText(f"🔒 {owner} is editing")' in source


def test_finish_clears_former_owner_waiting_projection():
    source = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")

    finish_index = source.index("success = self._transaction.finish_editing(")
    clear_index = source.index("self._snapshot_waiting_requests = []", finish_index)
    assert clear_index > finish_index
