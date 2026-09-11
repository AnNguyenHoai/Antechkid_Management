from pathlib import Path


SHELL = Path("src/centermanager/ui/student_workspace/student_workspace_shell.py").read_text(encoding="utf-8")
DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")


def test_workspace_centrally_projects_write_state():
    assert "self._write_enabled = enabled" in SHELL
    assert "self.dashboard_page, self.list_page, self.detail_page" in SHELL


def test_detail_propagates_write_state_to_all_mutation_children():
    for name in ("self.quick_actions", "self.assessment_section", "self.notes_widget", "self.documents_widget"):
        assert name in DETAIL
    assert "hasattr(widget, \"set_write_enabled\")" in DETAIL


def test_write_grant_and_release_drive_same_projection():
    assert "self.set_write_enabled(True)" in SHELL
    assert "self.set_write_enabled(False)" in SHELL
