"""Regression: Student operational defaults and export scope are explicit."""
from types import SimpleNamespace

from centermanager.ui.student_workspace.student_list_page import StudentListPage


def test_export_filtered_fetches_all_server_pages_and_keeps_sorting():
    calls = []
    students = [SimpleNamespace(id=i) for i in range(501)]
    class Students:
        def search_students_page(self, **kwargs):
            calls.append(kwargs)
            offset = (kwargs["page"] - 1) * kwargs["per_page"]
            return students[offset:offset + kwargs["per_page"]], len(students)
    page = object.__new__(StudentListPage)
    page._advanced_filter_active = False
    page._advanced_filter_criteria = None
    page._student_service = Students()
    page._sort_key, page._sort_asc = "student_code", False
    page._toolbar_filter_values = lambda: SimpleNamespace(
        status="ACTIVE", enrollment_status="enrolled", assessment_status=None,
    )
    page.search_bar = SimpleNamespace(text=lambda: "HS")
    result = StudentListPage._students_matching_export_filters(page)
    assert [item.id for item in result] == list(range(501))
    assert [item["page"] for item in calls] == [1, 2, 3]
    assert all(item["status"] == "ACTIVE" and item["search_text"] == "HS" for item in calls)
    assert all(item["sort_by"] == "student_code" and item["ascending"] is False for item in calls)


def test_advanced_filter_export_reuses_complete_visible_set_without_other_query():
    page = object.__new__(StudentListPage)
    page._advanced_filter_active = True
    page._advanced_filter_criteria = object()
    page._filtered = [SimpleNamespace(id=4), SimpleNamespace(id=7)]
    assert [s.id for s in StudentListPage._students_matching_export_filters(page)] == [4, 7]


def test_export_aborts_when_result_set_changes_mid_pagination():
    class Students:
        def search_students_page(self, **kwargs):
            if kwargs["page"] == 1:
                return [SimpleNamespace(id=i) for i in range(250)], 251
            return [], 250
    page = object.__new__(StudentListPage)
    page._advanced_filter_active = False
    page._advanced_filter_criteria = None
    page._student_service = Students()
    page._sort_key, page._sort_asc = "student_code", True
    page._toolbar_filter_values = lambda: SimpleNamespace(
        status="ACTIVE", enrollment_status=None, assessment_status=None,
    )
    page.search_bar = SimpleNamespace(text=lambda: "")
    import pytest
    with pytest.raises(RuntimeError, match="changed during export"):
        StudentListPage._students_matching_export_filters(page)


def test_active_export_filters_archived_even_if_repository_list_active_does_not():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/student_export_service.py").read_text(encoding="utf-8")
    assert 'student.status == "ACTIVE"' in source
    overview = (root / "src/centermanager/ui/student_workspace/student_overview_page.py").read_text(encoding="utf-8")
    assert "self.status.setCurrentIndex(1)" in overview
    listing = (root / "src/centermanager/ui/student_workspace/student_list_page.py").read_text(encoding="utf-8")
    assert 'self.search_bar.set_filter_value("status", "Active")' in listing
    assert "Export filtered" in listing and "Export all Active" in listing
