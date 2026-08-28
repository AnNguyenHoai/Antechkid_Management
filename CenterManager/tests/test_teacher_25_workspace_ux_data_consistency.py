from pathlib import Path

LIST = Path("src/centermanager/ui/teacher_workspace/teacher_list_page.py").read_text(encoding="utf-8")
SHELL = Path("src/centermanager/ui/teacher_workspace/teacher_workspace_shell.py").read_text(encoding="utf-8")


def test_shell_does_not_double_connect_navigation_and_header_signals():
    assert "def _connect_signals" not in SHELL
    assert SHELL.count("self.nav.page_selected.connect(self.navigate_to)") == 1
    assert SHELL.count("self.header.back_home_clicked.connect(self.go_home.emit)") == 1


def test_cross_page_refresh_keeps_visible_detail_consistent():
    start = SHELL.index("def _refresh_teacher_views")
    end = SHELL.index("def set_write_enabled", start)
    body = SHELL[start:end]
    assert "self.list_page.refresh()" in body
    assert "self.dashboard_page.refresh()" in body
    assert "self.content_stack.currentWidget() is self.detail_page" in body
    assert "self.detail_page.load_teacher(self._current_teacher_id)" in body


def test_archived_rows_show_archived_lifecycle_state():
    assert '"ARCHIVED" if t.deleted_at is not None' in LIST


def test_archived_mode_disables_assignment_filter_and_add_action():
    start = LIST.index("def _on_status_filter_changed")
    end = LIST.index("def _on_assignment_filter_changed", start)
    body = LIST[start:end]
    assert "self.assignment_filter.setEnabled(not archived)" in body
    assert "self.add_btn.setEnabled(not archived)" in body


def test_write_mode_cannot_reenable_add_or_bulk_archive_in_archived_view():
    start = LIST.index("def set_write_enabled")
    body = LIST[start:]
    assert "enabled and self._status_filter != \"ARCHIVED\"" in body
