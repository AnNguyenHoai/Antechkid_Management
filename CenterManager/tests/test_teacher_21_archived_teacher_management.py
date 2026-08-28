from pathlib import Path

LIST = Path("src/centermanager/ui/teacher_workspace/teacher_list_page.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/teacher_workspace/teacher_detail_page.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/teacher_service.py").read_text(encoding="utf-8")


def test_archived_filter_is_available_and_loads_archived_teachers():
    assert 'self.status_filter.addItem("Archived", "ARCHIVED")' in LIST
    assert 'self._teacher_service.list_archived_teachers()' in LIST
    assert 'self._status_filter == "ARCHIVED"' in LIST


def test_archived_teacher_context_menu_restores_instead_of_editing():
    start = LIST.index("def _on_context_menu")
    end = LIST.index("def _restore_teacher", start)
    body = LIST[start:end]
    assert "Restore Teacher" in body
    assert "if teacher.deleted_at is not None:" in body


def test_restore_requires_write_and_uses_service():
    start = LIST.index("def _restore_teacher")
    end = LIST.index("def _edit_teacher", start)
    body = LIST[start:end]
    assert "ensure_write()" in body
    assert "restore_teacher(teacher_id)" in body


def test_detail_can_load_archived_teacher_and_exposes_restore():
    assert "get_archived_teacher(teacher_id)" in DETAIL
    assert 'PrimaryButton("↩ Restore")' in DETAIL
    assert "def _on_restore" in DETAIL
    assert "restore_teacher(self._current_teacher_id)" in DETAIL


def test_archived_teacher_mutation_controls_are_disabled():
    assert "archived = self._current_teacher.deleted_at is not None" in DETAIL
    assert "self.edit_btn.setEnabled(enabled and not archived)" in DETAIL
    assert "self.manage_classes_btn.setEnabled(enabled and not archived)" in DETAIL


def test_restore_service_contract_remains_lifecycle_safe():
    assert "TeacherNotDeletedError" in SERVICE
    assert "TeacherTimelineEventType.TEACHER_RESTORED" in SERVICE
    assert "TeacherRestored(" in SERVICE
