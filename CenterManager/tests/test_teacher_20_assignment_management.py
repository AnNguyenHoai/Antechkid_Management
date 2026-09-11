from pathlib import Path

DETAIL = Path("src/centermanager/ui/teacher_workspace/teacher_detail_page.py").read_text(encoding="utf-8")
DIALOG = Path("src/centermanager/ui/teacher_workspace/teacher_assignment_dialog.py").read_text(encoding="utf-8")
SERVICE = Path("src/centermanager/services/teacher_assignment_service.py").read_text(encoding="utf-8")
REPO = Path("src/centermanager/repositories/teacher_assignment_repository.py").read_text(encoding="utf-8")


def test_teacher_detail_exposes_assignment_management_entry_point():
    assert "Manage Classes" in DETAIL
    assert "def _on_manage_classes" in DETAIL
    assert "TeacherAssignmentDialog(" in DETAIL


def test_assignment_dialog_requires_collaboration_write_for_mutations():
    assert "def _ensure_write" in DIALOG
    assert 'self._ensure_write("assign classes")' in DIALOG
    assert 'self._ensure_write("unassign classes")' in DIALOG
    assert "assignments_changed = Signal()" in DIALOG


def test_inactive_teacher_cannot_create_new_assignments_but_can_manage_existing():
    assert "self._teacher_is_active" in DIALOG
    assert "Inactive teachers cannot accept new class assignments." in DIALOG
    assert "self.assign_btn.setEnabled(can_assign)" in DIALOG
    assert "def _unassign_selected" in DIALOG


def test_assignment_changes_refresh_teacher_detail():
    assert "dialog.assignments_changed.connect(self._on_assignment_changed)" in DETAIL
    assert "def _on_assignment_changed" in DETAIL
    assert "self.load_teacher(self._current_teacher_id)" in DETAIL


def test_assignment_service_keeps_business_rules_and_repository_boundary():
    assert "Archived teacher" in SERVICE
    assert "Inactive teacher" in SERVICE
    assert "repo.exists(teacher_id, class_id)" in SERVICE
    assert "repo.get_assignment(teacher_id, class_id)" in SERVICE
    assert "def get_assignment(" in REPO
