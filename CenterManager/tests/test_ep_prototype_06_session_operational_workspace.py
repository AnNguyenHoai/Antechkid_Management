"""EP-PROTOTYPE-06 — source-driven session operational workspace contract."""
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager" / "ui"
CLASS_DETAIL = SRC / "class_workspace" / "class_detail_page.py"
SCHEDULE = SRC / "class_workspace" / "class_schedule_widget.py"
SESSION_DIALOG = SRC / "session" / "session_dialog.py"
SESSION_DETAIL = SRC / "session" / "session_detail_dialog.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_node(source: str, name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method_node(node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(
        child for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name
    )


def test_ep_prototype_06_session_entry_remains_class_owned():
    source = _read(CLASS_DETAIL)
    cls = _class_node(source, "ClassDetailPage")
    overview = _method_node(cls, "_create_overview_tab")
    overview_source = ast.unparse(overview)

    assert "ClassScheduleWidget" in overview_source
    assert "SessionService" in source
    assert "_on_add_session" in source


def test_ep_prototype_06_schedule_loads_and_opens_session_detail():
    source = _read(SCHEDULE)
    cls = _class_node(source, "ClassScheduleWidget")
    load = _method_node(cls, "_load_sessions")
    detail = _method_node(cls, "_open_session_detail")

    load_source = ast.unparse(load)
    detail_source = ast.unparse(detail)

    assert "get_sessions_for_class" in load_source
    assert "SessionDetailDialog" in detail_source
    assert "session_id" in detail_source


def test_ep_prototype_06_session_detail_required_operational_context():
    source = _read(SESSION_DETAIL)
    cls = _class_node(source, "SessionDetailDialog")
    setup = _method_node(cls, "_setup_ui")
    overview = _method_node(cls, "_create_overview_tab")
    load = _method_node(cls, "_load_session")

    setup_source = ast.unparse(setup)
    overview_source = ast.unparse(overview)
    load_source = ast.unparse(load)

    assert "SessionAttendanceWidget" in setup_source
    assert "Attendance" in setup_source
    assert "Teaching Overview" in setup_source
    assert "_create_overview_tab" in setup_source

    assert "_create_header" in overview_source
    assert "_create_attendance_summary" in overview_source
    assert "_create_note_section" in overview_source
    assert "_create_highlight_section" in overview_source
    assert "_create_summary" in overview_source

    assert "get_session" in load_source
    assert "class_id" in load_source
    assert "set_session" in load_source


def test_ep_prototype_06_session_lifecycle_and_validation_stay_service_owned():
    source = _read(SESSION_DIALOG)
    cls = _class_node(source, "SessionDialog")
    save = _method_node(cls, "_save")
    save_source = ast.unparse(save)

    assert "create_session" in save_source
    assert "update_session" in save_source
    assert "SessionValidationError" in source
    assert "Title is required" in save_source
    assert "Start time must be before end time" in save_source


def test_ep_prototype_06_session_reporting_is_read_only_operational_hook():
    source = _read(SCHEDULE)
    cls = _class_node(source, "ClassScheduleWidget")
    export = _method_node(cls, "_export_session_pdf")
    export_source = ast.unparse(export)

    assert "generate_session_report" in export_source
    assert "WRITE" not in export_source


def test_ep_prototype_06_no_second_session_router_or_duplicate_service_layer():
    schedule = _read(SCHEDULE)
    detail = _read(SESSION_DETAIL)
    dialog = _read(SESSION_DIALOG)

    combined = "\n".join((schedule, detail, dialog))
    assert "SessionWorkspaceRouter" not in combined
    assert "SessionWorkspaceService" not in combined
    assert "SessionWorkspaceRepository" not in combined
