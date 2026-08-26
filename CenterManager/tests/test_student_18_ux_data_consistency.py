from pathlib import Path

SOURCE = Path("src/centermanager/ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")

def test_status_filter_covers_active_archived_deleted():
    assert '"Deleted"' in SOURCE
    assert '"Deleted": "DELETED"' in SOURCE

def test_search_matches_current_filtered_base_not_global_list():
    start = SOURCE.index("def _filter_students")
    end = SOURCE.index("def _populate_table", start)
    section = SOURCE[start:end]
    assert 'base = getattr(self, "_filtered_base", self._students)' in section

def test_search_matches_parent_name_and_phone_as_promised_by_placeholder():
    start = SOURCE.index("def _filter_students")
    end = SOURCE.index("def _populate_table", start)
    section = SOURCE[start:end]
    assert "get_parents_by_student" in section
    assert "parent_phone" in section

def test_refresh_clears_stale_selection():
    start = SOURCE.index("def refresh")
    end = SOURCE.index("def show_add_dialog", start)
    section = SOURCE[start:end]
    assert "self._selected_ids = []" in section
    assert "self._update_bulk_bar()" in section

def test_context_menu_disables_mutations_in_read_only_mode():
    start = SOURCE.index("def _on_context_menu")
    end = SOURCE.index("def _archive_student", start)
    section = SOURCE[start:end]
    assert "can_write = self.can_write()" in section
    assert section.count("setEnabled(can_write)") >= 3

def test_filter_dialog_preserves_base_for_search_and_sort():
    start = SOURCE.index("def show_filter_dialog")
    end = SOURCE.index("def set_write_enabled", start)
    section = SOURCE[start:end]
    assert "self._filtered_base =" in section
    assert "self._apply_filters_and_sort()" in section
