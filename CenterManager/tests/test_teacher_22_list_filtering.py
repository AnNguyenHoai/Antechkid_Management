from pathlib import Path

LIST = Path("src/centermanager/ui/teacher_workspace/teacher_list_page.py").read_text(encoding="utf-8")


def test_assignment_filter_options_are_available():
    assert 'self.assignment_filter.addItem("All Assignments", "ALL")' in LIST
    assert 'self.assignment_filter.addItem("Has Classes", "ASSIGNED")' in LIST
    assert 'self.assignment_filter.addItem("No Classes", "UNASSIGNED")' in LIST


def test_assignment_filter_reuses_loaded_teacher_data():
    start = LIST.index("def _filter_teachers")
    end = LIST.index("def _populate_table", start)
    body = LIST[start:end]
    assert 'self._assignment_filter == "ASSIGNED"' in body
    assert 'self._assignment_filter == "UNASSIGNED"' in body
    assert 'bool(t.assigned_classes)' in body
    assert 'not bool(t.assigned_classes)' in body


def test_assignment_filter_does_not_trigger_extra_service_query():
    start = LIST.index("def _on_assignment_filter_changed")
    end = LIST.index("def _on_sort", start)
    body = LIST[start:end]
    assert "self._apply_filters_and_sort()" in body
    assert "refresh()" not in body


def test_status_and_assignment_filters_are_composable():
    start = LIST.index("def _filter_teachers")
    end = LIST.index("def _populate_table", start)
    body = LIST[start:end]
    assert 'self._status_filter == "ACTIVE"' in body
    assert 'self._status_filter == "INACTIVE"' in body
    assert 'self._assignment_filter == "ASSIGNED"' in body
    assert 'self._assignment_filter == "UNASSIGNED"' in body


def test_archived_filter_remains_separate_from_current_status_filters():
    assert 'self._teacher_service.list_archived_teachers()' in LIST
    assert 'self._status_filter == "ARCHIVED"' in LIST
    assert 'self.status_filter.addItem("Archived", "ARCHIVED")' in LIST
