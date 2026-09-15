from pathlib import Path

LIST = Path("src/centermanager/ui/teacher_workspace/teacher_list_page.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/teacher_workspace/teacher_workspace_shell.py").read_text(encoding="utf-8")


def test_list_exposes_teacher_changed_signal_for_successful_mutations():
    assert "teacher_changed = Signal()" in LIST


def test_shell_subscribes_to_list_mutation_signal():
    assert "self.list_page.teacher_changed.connect(self._on_teacher_changed)" in SHELL


def test_cross_page_refresh_updates_dashboard_and_list():
    start = SHELL.index("def _refresh_teacher_views")
    end = SHELL.index("def set_write_enabled", start)
    body = SHELL[start:end]
    assert "self.list_page.refresh()" in body
    assert "self.dashboard_page.refresh()" in body


def test_detail_mutations_use_same_cross_page_refresh_path():
    start = SHELL.index("def _on_teacher_updated")
    end = SHELL.index("def _on_teacher_changed", start)
    body = SHELL[start:end]
    assert "self._refresh_teacher_views()" in body


def test_successful_list_add_edit_restore_and_archive_emit_change():
    for marker in [
        "self._teacher_service.restore_teacher(teacher_id)",
        "self._teacher_service.delete_teacher(teacher_id)",
        "if dialog.exec() == TeacherFormDialog.DialogCode.Accepted:",
    ]:
        start = LIST.index(marker)
        body = LIST[start:start+350]
        assert "self.teacher_changed.emit()" in body
