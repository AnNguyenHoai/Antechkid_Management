from pathlib import Path

ASSIGN = Path("src/centermanager/ui/class_workspace/class_assignment_dialog.py").read_text(encoding="utf-8")
ENROLL = Path("src/centermanager/ui/class_workspace/class_enrollment_dialog.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/class_workspace/class_detail_page.py").read_text(encoding="utf-8")


def test_class_assignment_dialog_has_role_and_write_guards():
    assert "RoleDefinitions.ADMIN" in ASSIGN
    assert "RoleDefinitions.MANAGER" in ASSIGN
    assert "def _ensure_assignment_write" in ASSIGN
    assert 'if not self._ensure_assignment_write("assign a teacher"):' in ASSIGN
    assert 'if not self._ensure_assignment_write("remove a teacher"):' in ASSIGN


def test_class_enrollment_dialog_has_write_guards():
    assert "def _ensure_enrollment_write" in ENROLL
    assert 'if not self._ensure_enrollment_write("enroll students"):' in ENROLL
    assert 'if not self._ensure_enrollment_write("remove students"):' in ENROLL


def test_class_dialogs_do_not_create_production_engines():
    assert "create_production_engine" not in ASSIGN
    assert "create_production_engine" not in ENROLL


def test_class_detail_disables_dynamic_actions_in_read_mode():
    assert "def _apply_dynamic_write_state" in DETAIL
    assert "button.setEnabled(teacher_enabled)" in DETAIL
    assert "can_mutate = self._write_enabled and not self._archived_read_only" in DETAIL
    assert "button.setEnabled(can_mutate)" in DETAIL
    assert "teacher_enabled = can_mutate and self._can_manage_teacher_assignments()" in DETAIL
