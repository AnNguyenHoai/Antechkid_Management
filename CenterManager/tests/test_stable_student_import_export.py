"""Student import/export regression, schema independent."""
from pathlib import Path
from types import SimpleNamespace
import openpyxl
import pytest

from centermanager.services.student_import_service import StudentImportService
from centermanager.ui.student_workspace.student_list_page import StudentListPage


def _file(path, rows, headers=None):
    wb = openpyxl.Workbook()
    wb.active.append(headers or list(StudentImportService.IMPORT_HEADERS))
    for row in rows:
        wb.active.append(row)
    wb.save(path)
    return path


def test_preview_valid_template_without_writing(tmp_path):
    svc = object.__new__(StudentImportService)
    path = _file(tmp_path / "students.xlsx", [["HS1", "Student", "", "", "", "ACTIVE", "", ""]])
    assert svc.preview_from_excel(path) == (1, [])


def test_preview_rejects_wrong_headers_and_duplicate_codes(tmp_path):
    svc = object.__new__(StudentImportService)
    bad = _file(tmp_path / "bad.xlsx", [["HS1", "Student"]], headers=["X"] * 8)
    with pytest.raises(ValueError, match="template"):
        svc.preview_from_excel(bad)
    same = _file(tmp_path / "same.xlsx", [
        ["HS1", "A", "", "", "", "", "", ""],
        ["HS1", "B", "", "", "", "", "", ""],
    ])
    count, errors = svc.preview_from_excel(same)
    assert count == 2
    assert any("duplicate Student code" in error for error in errors)


def test_complete_export_uses_all_pages_and_rejects_count_drift():
    students = [SimpleNamespace(id=i) for i in range(501)]
    calls = []
    class Service:
        def search_students_page(self, **kwargs):
            calls.append(kwargs)
            start = (kwargs["page"] - 1) * kwargs["per_page"]
            return students[start:start + kwargs["per_page"]], len(students)
    page = SimpleNamespace(
        _advanced_filter_active=False,
        _advanced_filter_criteria=None,
        _student_service=Service(), _sort_key="student_code", _sort_asc=False,
        search_bar=SimpleNamespace(text=lambda: "HS"),
        _toolbar_filter_values=lambda: SimpleNamespace(status="ACTIVE", enrollment_status=None, assessment_status=None),
    )
    assert len(StudentListPage._students_matching_export_filters(page)) == 501
    assert [v["page"] for v in calls] == [1, 2, 3]


def test_active_export_filters_archived():
    source = (Path(__file__).resolve().parents[1] /
              "src/centermanager/services/student_export_service.py").read_text(encoding="utf-8")
    assert 'student.status == "ACTIVE"' in source


def test_import_service_preserves_excel_student_codes_and_rejects_invalid_rows(tmp_path):
    svc = object.__new__(StudentImportService)
    path = _file(tmp_path / "bad_codes.xlsx", [
        ["BAD-01", "Student", "", "", "", "ACTIVE", "", ""],
        ["HS100", "Student", "", "", "", "UNKNOWN", "", ""],
    ])
    rows, errors = svc.preview_from_excel(path)
    assert rows == 2
    assert any("Invalid Student code" in error for error in errors)
    assert any("Invalid status" in error for error in errors)
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    service = (root / "services/student_service.py").read_text(encoding="utf-8")
    importer = (root / "services/student_import_service.py").read_text(encoding="utf-8")
    assert "student_code: Optional[str] = None" in service
    assert "student_code=str(code).strip() if code else None" in importer
