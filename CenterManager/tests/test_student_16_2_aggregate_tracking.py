from pathlib import Path
MAIN = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
COLLAB = Path("src/centermanager/platform/collaboration/collaboration_manager.py").read_text(encoding="utf-8")

def test_parent_events_mark_owning_student_dirty():
    assert 'student_id = getattr(event, "student_id", None)' in MAIN
    assert 'self._transaction.mark_student_dirty(student_id)' in MAIN

def test_student_lifecycle_events_mark_student_dirty():
    assert MAIN.count('self._transaction.mark_student_dirty(event.student_id)') >= 3

def test_renew_and_release_are_serialized():
    section = COLLAB[COLLAB.index("def renew_remote_lease"):COLLAB.index("def heartbeat")]
    assert "with self._state_mutex:" in section
