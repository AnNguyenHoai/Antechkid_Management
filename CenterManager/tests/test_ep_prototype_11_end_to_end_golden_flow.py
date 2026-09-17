"""Source-driven regression contract for EP-PROTOTYPE-11."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "src" / "centermanager" / "ui" / "main_window.py"
HOME = ROOT / "src" / "centermanager" / "ui" / "home" / "home_page.py"
STUDENT_SHELL = ROOT / "src" / "centermanager" / "ui" / "student_workspace" / "student_workspace_shell.py"
STUDENT_DETAIL = ROOT / "src" / "centermanager" / "ui" / "student_workspace" / "student_detail_page.py"
CLASS_DETAIL = ROOT / "src" / "centermanager" / "ui" / "class_workspace" / "class_detail_page.py"
SESSION_DETAIL = ROOT / "src" / "centermanager" / "ui" / "session" / "session_detail_dialog.py"
FINANCE_SHELL = ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "finance_workspace_shell.py"


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


def test_ep_prototype_11_home_to_workspace_selection_contract():
    home_source = _read(HOME)
    home_cls = _class_node(home_source, "HomePage")
    clicked = _method_node(home_cls, "_on_workspace_clicked")
    clicked_source = ast.unparse(clicked)

    main_source = _read(MAIN_WINDOW)
    main_cls = _class_node(main_source, "MainWindow")
    selected = _method_node(main_cls, "_on_workspace_selected")
    selected_source = ast.unparse(selected)

    assert "workspace_selected.emit" in clicked_source
    for workspace_id in ("student", "teacher", "class", "finance", "employee", "admin"):
        assert workspace_id in selected_source
    assert "central_stack.setCurrentWidget" in selected_source


def test_ep_prototype_11_application_shell_wires_cross_workspace_signals():
    source = _read(MAIN_WINDOW)
    cls = _class_node(source, "MainWindow")

    home_setup = _method_node(cls, "_setup_home")
    student_setup = _method_node(cls, "_setup_student_workspace")
    teacher_setup = _method_node(cls, "_setup_teacher_workspace")
    class_setup = _method_node(cls, "_setup_class_workspace")
    finance_setup = _method_node(cls, "_setup_finance_workspace")

    assert "workspace_selected.connect" in ast.unparse(home_setup)
    assert "student_workspace.go_home.connect" in ast.unparse(student_setup)
    assert "student_workspace.go_to_finance.connect" in ast.unparse(student_setup)
    assert "teacher_workspace.go_home.connect" in ast.unparse(teacher_setup)
    assert "teacher_workspace.navigate_to_class.connect" in ast.unparse(teacher_setup)
    assert "class_workspace.go_home.connect" in ast.unparse(class_setup)
    assert "finance_workspace.go_home.connect" in ast.unparse(finance_setup)


def test_ep_prototype_11_student_flow_connects_detail_to_operational_surfaces():
    shell_source = _read(STUDENT_SHELL)
    shell_cls = _class_node(shell_source, "StudentWorkspaceShell")
    setup = _method_node(shell_cls, "_setup_ui")
    selected = _method_node(shell_cls, "_on_student_selected")
    setup_source = ast.unparse(setup)
    selected_source = ast.unparse(selected)

    assert "StudentDetailPage" in setup_source
    assert "timeline_service" in setup_source
    assert "assessment_service" in setup_source
    assert "attendance_service" in setup_source
    assert "enrollment_service" in setup_source
    assert "load_student" in selected_source
    assert "setCurrentWidget" in selected_source

    detail_source = _read(STUDENT_DETAIL)
    detail_cls = _class_node(detail_source, "StudentDetailPage")
    setup_detail = _method_node(detail_cls, "_setup_ui")
    profile = _method_node(detail_cls, "_create_profile_tab")
    populate = _method_node(detail_cls, "_populate_profile")
    setup_detail_source = ast.unparse(setup_detail)
    profile_source = ast.unparse(profile)
    populate_source = ast.unparse(populate)

    # These surfaces are intentionally split across StudentDetailPage helpers:
    # Enrollment and Attendance are top-level tabs created by _setup_ui, while
    # Assessment and Timeline belong to the Profile tab.
    assert "EnrollmentWidget" in setup_detail_source
    assert "StudentAttendanceWidget" in setup_detail_source
    assert "AssessmentSection" in profile_source
    assert "TimelineWidget" in profile_source
    assert "get_student_timeline" in populate_source


def test_ep_prototype_11_class_to_session_flow_is_composed_in_class_workspace():
    source = _read(CLASS_DETAIL)
    cls = _class_node(source, "ClassDetailPage")
    overview = _method_node(cls, "_create_overview_tab")
    overview_source = ast.unparse(overview)

    assert "ClassScheduleWidget" in overview_source
    assert "session_service" in overview_source
    assert "timeline" in overview_source.lower()


def test_ep_prototype_11_session_to_attendance_and_teaching_overview():
    source = _read(SESSION_DETAIL)
    cls = _class_node(source, "SessionDetailDialog")
    setup = _method_node(cls, "_setup_ui")
    setup_source = ast.unparse(setup)

    assert "Attendance" in setup_source
    assert "Teaching Overview" in setup_source
    assert "SessionAttendanceWidget" in setup_source


def test_ep_prototype_11_finance_remains_an_existing_workspace_surface():
    source = _read(FINANCE_SHELL)
    cls = _class_node(source, "FinanceWorkspaceShell")
    setup = _method_node(cls, "_setup_ui")
    setup_source = ast.unparse(setup)

    for surface in ("Dashboard", "Income", "Expense", "Outstanding"):
        assert surface in setup_source


def test_ep_prototype_11_return_home_refreshes_existing_home_surface():
    source = _read(MAIN_WINDOW)
    cls = _class_node(source, "MainWindow")
    go_home = _method_node(cls, "_go_home")
    go_home_source = ast.unparse(go_home)

    assert "home_page" in go_home_source
    assert "refresh" in go_home_source
    assert "central_stack.setCurrentWidget" in go_home_source


def test_ep_prototype_11_no_second_application_router_or_persistence_path():
    combined = "\n".join(
        _read(path)
        for path in (
            MAIN_WINDOW,
            HOME,
            STUDENT_SHELL,
            STUDENT_DETAIL,
            CLASS_DETAIL,
            SESSION_DETAIL,
            FINANCE_SHELL,
        )
    )
    for name in ("ApplicationRouter", "DashboardRouter", "WorkspaceRouter", "HomeDashboardRouter"):
        assert name not in combined
