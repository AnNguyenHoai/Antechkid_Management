from pathlib import Path

DETAIL = Path("src/centermanager/ui/student_workspace/student_detail_page.py").read_text(encoding="utf-8")
REPORTS = Path("src/centermanager/ui/student_workspace/report_list_widget.py").read_text(encoding="utf-8")


def test_detail_has_single_authoritative_refresh_path():
    assert "def refresh_current_student" in DETAIL
    assert "self.load_student(self._current_student_id)" in DETAIL
    changed = DETAIL[DETAIL.index("def _on_data_changed"):DETAIL.index("def _export_pdf")]
    assert "self.refresh_current_student()" in changed


def test_load_refreshes_all_detail_surfaces():
    load = DETAIL[DETAIL.index("def load_student"):DETAIL.index("def _populate_profile")]
    for call in ("self._populate_profile(student)", "self._populate_financial(student.id)",
                 "self._populate_attendance(student.id)", "self.report_list_widget.set_student(student.id)"):
        assert call in load


def test_write_mode_covers_parent_mutation_controls():
    assert "self._parent_mutation_buttons" in DETAIL
    assert "add_btn.setEnabled(self._write_enabled)" in DETAIL
    assert "for button in self._parent_mutation_buttons" in DETAIL


def test_financial_changes_refresh_detail_and_notify_shell():
    assert "self.financial_tab.financial_updated.connect(self._on_data_changed)" in DETAIL


def test_report_write_mode_repaints_existing_rows():
    method = REPORTS[REPORTS.index("def set_write_enabled"):]
    assert "self._update_list()" in method
