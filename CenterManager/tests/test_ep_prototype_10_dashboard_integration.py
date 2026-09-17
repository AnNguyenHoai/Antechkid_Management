"""Source-driven regression contract for EP-PROTOTYPE-10."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "src" / "centermanager" / "ui" / "home" / "home_page.py"
CARD = ROOT / "src" / "centermanager" / "ui" / "home" / "workspace_card.py"
HOME_SERVICE = ROOT / "src" / "centermanager" / "services" / "home_dashboard_service.py"
MAIN_WINDOW = ROOT / "src" / "centermanager" / "ui" / "main_window.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _class_node(source: str, name: str) -> ast.ClassDef:
    tree = ast.parse(source)
    return next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)


def _method_node(node: ast.ClassDef, name: str):
    return next(
        child for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name
    )


def test_ep_prototype_10_home_dashboard_loads_workspace_summaries():
    source = _read(HOME)
    cls = _class_node(source, "HomePage")
    refresh = _method_node(cls, "refresh")
    populate = _method_node(cls, "_populate_workspace_cards")
    refresh_source = ast.unparse(refresh)
    populate_source = ast.unparse(populate)

    assert "_populate_workspace_cards" in refresh_source
    assert "get_workspace_summaries" in populate_source
    assert "WorkspaceCard" in populate_source
    assert "workspace_id" in populate_source


def test_ep_prototype_10_workspace_card_emits_stable_selection_id():
    source = _read(CARD)
    cls = _class_node(source, "WorkspaceCard")
    setup = _method_node(cls, "_setup_ui")
    mouse_press = _method_node(cls, "mousePressEvent")
    setup_source = ast.unparse(setup)
    mouse_source = ast.unparse(mouse_press)

    assert "self._workspace_id" in source
    assert "clicked.emit" in setup_source
    assert "self._workspace_id" in setup_source
    assert "clicked.emit" in mouse_source


def test_ep_prototype_10_home_service_owns_aggregation():
    source = _read(HOME_SERVICE)
    cls = _class_node(source, "HomeDashboardService")
    get_summaries = _method_node(cls, "get_workspace_summaries")
    method_source = ast.unparse(get_summaries)

    assert "_session_factory" in method_source
    assert "_repository_provider" in method_source
    assert "WorkspaceSummary" in method_source
    assert "student_repo" in method_source
    assert "class_repo" in method_source
    assert "teacher_repo" in method_source
    assert "finance" in method_source


def test_ep_prototype_10_main_window_owns_application_workspace_routing():
    source = _read(MAIN_WINDOW)
    cls = _class_node(source, "MainWindow")
    selected = _method_node(cls, "_on_workspace_selected")
    go_home = _method_node(cls, "_go_home")
    selected_source = ast.unparse(selected)
    go_home_source = ast.unparse(go_home)

    # ast.unparse() normalizes string literals to its own quoting style, so
    # validate the semantic workspace identifiers rather than the source-level
    # quote character used in the dictionary/condition literals.
    for workspace_id in ("student", "teacher", "class", "finance", "employee", "admin"):
        assert workspace_id in selected_source

    assert "permission_map" in selected_source
    assert "teacher.view" in selected_source
    assert "class.view" in selected_source
    assert "finance.view" in selected_source
    assert "user.manage" in selected_source
    assert "central_stack.setCurrentWidget" in selected_source
    assert "home_page.refresh" in go_home_source


def test_ep_prototype_10_no_parallel_application_router_is_introduced():
    combined = "\n".join((_read(HOME), _read(CARD), _read(HOME_SERVICE), _read(MAIN_WINDOW)))
    for name in ("ApplicationRouter", "DashboardRouter", "WorkspaceRouter", "HomeDashboardRouter"):
        assert name not in combined
