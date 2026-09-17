"""Source-driven regression contract for EP-PROTOTYPE-04.

The current Class Workspace already provides the prototype flow, so this task
protects the existing structure without launching Qt or changing business
behavior.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"
CLASS_WS = SRC / "ui" / "class_workspace"
SHELL = CLASS_WS / "class_workspace_shell.py"
LIST_PAGE = CLASS_WS / "class_list_page.py"
DETAIL_PAGE = CLASS_WS / "class_detail_page.py"


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


def test_ep_prototype_04_class_workspace_shell_contract():
    source = _read(SHELL)
    cls = _class_node(source, "ClassWorkspaceShell")

    assert "go_home" in _source_names(cls)
    assert "QStackedWidget" in source
    assert "WorkspaceNavigation" in source
    assert "ClassDashboardPage" in source
    assert "ClassListPage" in source
    assert "ClassDetailPage" in source

    setup = _method_node(cls, "_setup_ui")
    names = _source_names(setup)
    for required in ("ClassDashboardPage", "ClassListPage", "ClassDetailPage"):
        assert required in names

    for page_id in ("dashboard", "classes"):
        assert page_id in source

    assert "self.content_stack.addWidget(self.dashboard_page)" in source
    assert "self.content_stack.addWidget(self.list_page)" in source
    assert "self.content_stack.addWidget(self.detail_page)" in source


def test_ep_prototype_04_class_selection_converges_on_detail():
    source = _read(SHELL)
    cls = _class_node(source, "ClassWorkspaceShell")

    selection = _method_node(cls, "_on_class_selected")
    names = _source_names(selection)
    selection_source = ast.unparse(selection)

    assert "_current_class_id" in names
    assert "load_class" in names
    assert "detail_page" in names
    assert "setCurrentWidget" in names
    assert "self.detail_page.load_class(class_id)" in selection_source


def test_ep_prototype_04_class_detail_required_context():
    source = _read(DETAIL_PAGE)
    cls = _class_node(source, "ClassDetailPage")
    overview = _method_node(cls, "_create_overview_tab")
    overview_source = ast.unparse(overview)

    # Core class identity/context rendered by the overview tab.
    assert "name_label" in overview_source
    assert "status_badge" in overview_source
    assert "course_label" in overview_source

    # Stats are constructed by their dedicated helper and embedded in the overview.
    stats = _method_node(cls, "_create_stats")
    stats_source = ast.unparse(stats)
    assert "students_label" in stats_source
    assert "capacity_label" in stats_source
    assert "self.stats_widget = self._create_stats()" in overview_source

    # Golden Flow context: teacher, students, sessions and timeline.
    assert "Assigned Teacher" in overview_source
    assert "Enrolled Students" in overview_source
    assert "ClassScheduleWidget" in overview_source
    assert "Add Session" in overview_source
    assert "TimelineWidget" in overview_source
    assert "📅 Timeline" in overview_source


def test_ep_prototype_04_class_detail_loads_selected_context():
    source = _read(DETAIL_PAGE)
    cls = _class_node(source, "ClassDetailPage")

    load_method = _method_node(cls, "load_class")
    load_source = ast.unparse(load_method)
    load_names = _source_names(load_method)

    assert "get_class_with_details" in load_names
    assert "_current_class_id" in load_names
    assert "_current_class" in load_names
    assert "_populate" in load_names
    assert "class_id" in load_names
    assert "self._populate(class_obj)" in load_source

    populate = _method_node(cls, "_populate")
    populate_source = ast.unparse(populate)
    assert "set_class" in _source_names(populate)
    assert "get_class_timeline" in _source_names(populate)
    assert "self.schedule_widget.set_class(class_obj.id)" in populate_source
    assert "self.timeline_widget.set_events(events)" in populate_source


def test_ep_prototype_04_back_navigation_returns_to_classes():
    source = _read(SHELL)
    cls = _class_node(source, "ClassWorkspaceShell")
    back_method = _method_node(cls, "_on_back_from_detail")
    back_source = ast.unparse(back_method)

    # AST unparse may normalize quote style; verify semantic routing.
    assert "navigate_to" in back_source
    assert "classes" in back_source
    assert "list_page" in back_source


def test_ep_prototype_04_write_boundary_remains_present():
    shell_source = _read(SHELL)
    list_source = _read(LIST_PAGE)
    detail_source = _read(DETAIL_PAGE)

    assert "set_write_enabled" in shell_source
    assert "ensure_write" in list_source
    assert "ensure_write" in detail_source
    assert "_write_enabled" in detail_source


def test_ep_prototype_04_no_second_class_router_or_service_layer():
    shell_source = _read(SHELL)

    assert "QStackedWidget" in shell_source
    assert "WorkspaceNavigation" in shell_source
    assert "ClassService" not in shell_source
    assert "Repository" not in shell_source
