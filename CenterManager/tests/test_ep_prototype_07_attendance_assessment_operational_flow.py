"""EP-PROTOTYPE-07 — source-driven attendance and assessment contract."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "ui"
SESSION_DETAIL = SRC / "session" / "session_detail_dialog.py"
SESSION_ATTENDANCE = SRC / "session" / "session_attendance_widget.py"
STUDENT_ATTENDANCE = SRC / "student_workspace" / "student_attendance_widget.py"
ASSESSMENT_SECTION = SRC / "assessment" / "assessment_section.py"
ASSESSMENT_DIALOG = SRC / "assessment" / "assessment_dialog.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_node(source: str, name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method_node(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(child for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name)


def test_ep_prototype_07_session_owns_operational_attendance():
    source = _read(SESSION_DETAIL)
    cls = _class_node(source, "SessionDetailDialog")
    setup = _method_node(cls, "_setup_ui")
    load = _method_node(cls, "_load_session")
    assert "SessionAttendanceWidget" in ast.unparse(setup)
    assert "Attendance" in ast.unparse(setup)
    assert "set_session" in ast.unparse(load)
    assert "_on_attendance_changed" in source


def test_ep_prototype_07_attendance_editing_stays_service_owned():
    source = _read(SESSION_ATTENDANCE)
    cls = _class_node(source, "SessionAttendanceWidget")
    load = _method_node(cls, "_load_data")
    save = _method_node(cls, "_save_attendance")
    load_source = ast.unparse(load)
    save_source = ast.unparse(save)
    assert "get_attendance_for_session" in load_source
    assert "get_class_with_details" in load_source
    assert "create_or_update_attendance" in save_source
    assert "AttendanceService" in source
    assert "Repository" not in save_source


def test_ep_prototype_07_student_attendance_is_read_only():
    source = _read(STUDENT_ATTENDANCE)
    cls = _class_node(source, "StudentAttendanceWidget")
    setup = _method_node(cls, "_setup_ui")
    load = _method_node(cls, "_load_data")
    assert "NoEditTriggers" in ast.unparse(setup)
    assert "get_attendance_for_student" in ast.unparse(load)
    assert "get_attendance_rate_for_student" in ast.unparse(load)
    assert "create_or_update_attendance" not in ast.unparse(load)


def test_ep_prototype_07_assessment_section_owns_latest_and_history():
    source = _read(ASSESSMENT_SECTION)
    cls = _class_node(source, "AssessmentSection")
    load = _method_node(cls, "_load_data")
    add = _method_node(cls, "_on_add")
    view = _method_node(cls, "_on_view")
    assert "get_latest_assessment" in ast.unparse(load)
    assert "get_assessments_for_student" in ast.unparse(load)
    assert "AssessmentDialog" in ast.unparse(add)
    assert "AssessmentDetailDialog" in ast.unparse(view)
    assert "assessment_changed" in source


def test_ep_prototype_07_assessment_persistence_and_validation_stay_service_owned():
    source = _read(ASSESSMENT_DIALOG)
    cls = _class_node(source, "AssessmentDialog")
    save_source = ast.unparse(_method_node(cls, "_save"))
    assert "create_assessment" in save_source
    assert "update_assessment" in save_source
    assert "AssessmentValidationError" in source
    assert "except AssessmentValidationError" in save_source


def test_ep_prototype_07_assessment_dialog_has_required_qt_type_imports():
    source = _read(ASSESSMENT_DIALOG)
    tree = ast.parse(source)
    imported_names = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets"
        for alias in node.names
    }
    assert "QWidget" in imported_names


def test_ep_prototype_07_no_duplicate_operational_layers():
    combined = "\n".join((_read(SESSION_DETAIL), _read(SESSION_ATTENDANCE), _read(ASSESSMENT_SECTION), _read(ASSESSMENT_DIALOG)))
    for name in ("AttendanceWorkspaceRouter", "AssessmentWorkspaceRouter", "AttendanceWorkspaceService", "AssessmentWorkspaceService", "AttendanceWorkspaceRepository", "AssessmentWorkspaceRepository"):
        assert name not in combined
