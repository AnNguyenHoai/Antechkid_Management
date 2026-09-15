from pathlib import Path
SOURCE = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
def test_writer_ui_does_not_project_waiting_count():
    assert "⚠️ Waiting:" not in SOURCE
    assert "✏️ You are editing" in SOURCE
def test_non_writer_sees_current_editor():
    assert "🔒 {owner_text} is editing" in SOURCE
def test_idle_ui_shows_no_active_editor():
    assert "● No active editor" in SOURCE
def test_waiting_status_is_not_driven_by_write_requested_event():
    assert "def _on_write_requested" not in SOURCE
