"""C-01: Archived class history is inspectable without enabling writes."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "centermanager"
CLASSES = ROOT / "services" / "class_service.py"
DETAIL = ROOT / "ui" / "class_workspace" / "class_detail_page.py"
LIST = ROOT / "ui" / "class_workspace" / "class_list_page.py"
SCHEDULE = ROOT / "ui" / "class_workspace" / "class_schedule_widget.py"
SESSION = ROOT / "ui" / "session" / "session_detail_dialog.py"


def source(path):
    data = path.read_text(encoding="utf-8")
    ast.parse(data)
    return data


def test_archived_class_has_dedicated_read_endpoint_and_active_mutation_guard():
    service = source(CLASSES)
    assert "def get_archived_class_with_details" in service
    assert "def get_historical_enrolled_students" in service
    assert "enrollments = self._repository_provider.enrollments(session).get_by_class_with_student(class_id)" in service
    assert "def _require_active_class" in service
    assert "ClassArchivedError" in service


def test_archived_class_list_opens_detail_without_restoring():
    src = source(LIST)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ClassListPage")
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_on_row_double_clicked")
    body = ast.unparse(method)
    assert "self.class_selected.emit(class_obj.id)" in body
    assert "deleted_at" not in body
    assert "restore_class(class_id)" in src


def test_detail_marks_history_and_disables_all_mutating_actions():
    src = source(DETAIL)
    assert "get_archived_class_with_details" in src
    assert "get_historical_enrolled_students" in src
    assert "ARCHIVED · READ ONLY" in src
    assert "allowed = enabled and not self._archived_read_only" in src
    assert "can_mutate = self._write_enabled and not self._archived_read_only" in src
    assert "self.schedule_widget.set_write_enabled(allowed)" in src


def test_archived_session_detail_blocks_attendance_notes_highlights_and_session_edit():
    src = source(SCHEDULE)
    detail = source(SESSION)
    assert "dialog.set_historical_read_only(True)" in src
    assert "def set_historical_read_only(self, enabled: bool = True)" in detail
    for control in ("edit_btn", "attendance_widget", "note_widget", "highlight_widget"):
        assert f"self.{control}.setEnabled(not enabled)" in detail


def test_normal_class_detail_preserves_active_path():
    src = source(DETAIL)
    assert "self._class_service.get_class_with_details(class_id)" in src
    assert "self._archived_read_only = class_obj.deleted_at is not None" in src
