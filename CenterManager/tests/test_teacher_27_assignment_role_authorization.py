from pathlib import Path

DETAIL = Path("src/centermanager/ui/teacher_workspace/teacher_detail_page.py").read_text(encoding="utf-8")
DIALOG = Path("src/centermanager/ui/teacher_workspace/teacher_assignment_dialog.py").read_text(encoding="utf-8")


def test_detail_assignment_button_is_limited_to_admin_and_manager():
    assert "from centermanager.models.role import RoleDefinitions" in DETAIL
    start = DETAIL.index("def _can_manage_class_assignments")
    end = DETAIL.index("def _on_manage_classes", start)
    body = DETAIL[start:end]
    assert "RoleDefinitions.ADMIN" in body
    assert "RoleDefinitions.MANAGER" in body


def test_detail_manage_classes_button_respects_role_authorization():
    assert "and self._can_manage_class_assignments()" in DETAIL


def test_detail_handler_has_runtime_role_guard():
    start = DETAIL.index("def _on_manage_classes")
    body = DETAIL[start:start+900]
    assert "if not self._can_manage_class_assignments():" in body
    assert "Only Admin or Manager accounts can manage teacher class assignments." in body


def test_assignment_dialog_disables_assign_and_unassign_for_other_roles():
    start = DIALOG.index("def _update_write_state")
    end = DIALOG.index("def _ensure_write", start)
    body = DIALOG[start:end]
    assert "self.assign_btn.setEnabled(can_assign)" in body
    assert "self.unassign_btn.setEnabled(role_allowed)" in body


def test_assignment_dialog_guards_both_mutations_at_runtime():
    assign = DIALOG[DIALOG.index("def _assign_selected"):DIALOG.index("def _unassign_selected")]
    unassign = DIALOG[DIALOG.index("def _unassign_selected"):]
    assert "if not self._can_manage_class_assignments():" in assign
    assert "if not self._can_manage_class_assignments():" in unassign
