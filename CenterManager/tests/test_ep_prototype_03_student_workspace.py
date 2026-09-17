"""Source-driven regression contract for EP-PROTOTYPE-03.

The prototype task is intentionally non-invasive: the current Student Workspace
already implements the required flow, so the tests protect the existing contract
without starting the Qt application or changing business behavior.
"""

from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"
STUDENT_WS = SRC / "ui" / "student_workspace"
SHELL = STUDENT_WS / "student_workspace_shell.py"
LIST_PAGE = STUDENT_WS / "student_list_page.py"
DETAIL_PAGE = STUDENT_WS / "student_detail_page.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_node(source: str, class_name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"Missing class: {class_name}")


def _method_node(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method_name:
            return node
    raise AssertionError(f"Missing method: {method_name}")


def _source_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def test_ep_prototype_03_student_workspace_shell_contract():
    source = _read(SHELL)
    cls = _class_node(source, "StudentWorkspaceShell")

    assert 'workspace_id="student"' in source
    assert 'Signal(int)' in source
    assert 'go_home = Signal()' in source
    assert 'go_to_finance = Signal()' in source

    setup = _method_node(cls, "_setup_ui")
    names = _source_names(setup)

    for required_page in ("StudentDashboardPage", "StudentListPage", "StudentDetailPage", "StudentAnalyticsPage"):
        assert required_page in names, f"Student Workspace must register {required_page}"

    assert '"dashboard"' in source
    assert '"students"' in source
    assert '"analytics"' in source
    assert "self.content_stack.addWidget(self.list_page)" in source
    assert "self.content_stack.addWidget(self.detail_page)" in source


def test_ep_prototype_03_student_selection_converges_on_detail():
    source = _read(SHELL)
    cls = _class_node(source, "StudentWorkspaceShell")

    list_selection = _method_node(cls, "_on_student_selected")
    dashboard_selection = _method_node(cls, "_on_student_selected_from_dashboard")

    list_names = _source_names(list_selection)
    dashboard_names = _source_names(dashboard_selection)

    assert "_current_student_id" in list_names
    assert "load_student" in list_names
    assert "detail_page" in list_names
    assert "student_selected" in list_names

    # Dashboard selection must converge on the same Student Detail handler.
    assert "_on_student_selected" in dashboard_names
    assert "self._on_student_selected(student_id)" in ast.unparse(dashboard_selection)


def test_ep_prototype_03_student_detail_required_context():
    source = _read(DETAIL_PAGE)
    cls = _class_node(source, "StudentDetailPage")
    setup = _method_node(cls, "_setup_ui")
    setup_source = ast.unparse(setup)

    assert "Profile" in setup_source
    assert "🎓 Enrollment" in setup_source
    assert "EnrollmentWidget" in setup_source

    # Timeline is part of the Profile tab's vertical content, not a separate tab.
    profile_method = _method_node(cls, "_create_profile_tab")
    profile_source = ast.unparse(profile_method)
    assert "📅 Timeline" in profile_source
    assert "TimelineWidget" in profile_source

    # Existing operational surfaces needed by the Golden Flow remain exposed.
    assert "AssessmentSection" in profile_source
    assert "StudentAttendanceWidget" in setup_source


def test_ep_prototype_03_detail_navigation_back_and_finance_hook():
    source = _read(DETAIL_PAGE)
    cls = _class_node(source, "StudentDetailPage")

    back_handler = _method_node(cls, "_setup_ui")
    back_source = ast.unparse(back_handler)
    assert "back_clicked.emit" in back_source
    assert "open_finance_clicked" in back_source

    shell_source = _read(SHELL)
    shell_cls = _class_node(shell_source, "StudentWorkspaceShell")
    back_method = _method_node(shell_cls, "_on_back_from_detail")
    back_method_source = ast.unparse(back_method)
    # AST unparse normalizes quote style; assert the route semantically, not its source spelling.
    assert "navigate_to" in back_method_source
    assert "students" in back_method_source


def test_ep_prototype_03_permission_and_write_boundaries_remain_present():
    shell_source = _read(SHELL)
    detail_source = _read(DETAIL_PAGE)

    assert "WriteGuard" in shell_source
    assert "PermissionGuard" in shell_source
    assert "WriteGuard" in detail_source
    assert 'has_permission("finance.view")' in detail_source
    assert "set_write_enabled" in shell_source


def test_ep_prototype_03_no_second_student_workspace_router_or_service_layer():
    shell_source = _read(SHELL)

    # The workspace must use its existing navigation stack rather than creating
    # a second application router or introducing a new student service boundary.
    assert "QStackedWidget" in shell_source
    assert "WorkspaceNavigation" in shell_source
    assert "StudentService" not in shell_source
    assert "Repository" not in shell_source
