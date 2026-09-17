"""Regression contract for EP-PROTOTYPE-02 application shell navigation."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_PATH = PROJECT_ROOT / "src" / "centermanager" / "ui" / "main_window.py"
HOME_PAGE_PATH = PROJECT_ROOT / "src" / "centermanager" / "ui" / "home" / "home_page.py"
APP_PATH = PROJECT_ROOT / "src" / "centermanager" / "app.py"

PROTOTYPE_WORKSPACES = {
    "student": "StudentWorkspaceShell",
    "class": "ClassWorkspaceShell",
    "teacher": "TeacherWorkspaceShell",
    "finance": "FinanceWorkspaceShell",
}


def _read(path: Path) -> str:
    assert path.is_file(), f"Required application-shell file missing: {path}"
    return path.read_text(encoding="utf-8")


def _parse(path: Path) -> ast.Module:
    return ast.parse(_read(path), filename=str(path))


def _main_window_class() -> ast.ClassDef:
    tree = _parse(MAIN_WINDOW_PATH)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MainWindow"]
    assert classes, "MainWindow class is missing"
    return classes[0]


def _method(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    methods = [node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert methods, f"MainWindow.{name}() is missing"
    return methods[0]


def _string_literals(node: ast.AST) -> set[str]:
    return {
        value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant)
        and isinstance((value := item.value), str)
    }


def test_ep_prototype_02_application_bootstrap_creates_main_window():
    text = _read(APP_PATH)
    assert "from centermanager.ui.main_window import MainWindow" in text
    assert "window = MainWindow(" in text
    assert "window.show()" in text


def test_ep_prototype_02_main_window_owns_application_page_stack():
    class_node = _main_window_class()
    init = _method(class_node, "__init__")
    literals = _string_literals(init)

    assert "QStackedWidget" in _read(MAIN_WINDOW_PATH)
    assert "central_stack" in literals or "central_stack" in _read(MAIN_WINDOW_PATH)
    assert "self.central_stack = QStackedWidget()" in _read(MAIN_WINDOW_PATH)
    assert "self.central_stack.setCurrentWidget(self.home_page)" in _read(MAIN_WINDOW_PATH)


def test_ep_prototype_02_home_exposes_single_workspace_selection_boundary():
    text = _read(HOME_PAGE_PATH)
    assert "workspace_selected = Signal(str)" in text
    assert "self.workspace_selected.emit(workspace_id)" in text
    assert "_on_workspace_clicked" in text


def test_ep_prototype_02_main_window_registers_all_core_prototype_workspaces():
    text = _read(MAIN_WINDOW_PATH)
    for workspace_id, shell_name in PROTOTYPE_WORKSPACES.items():
        assert shell_name in text, f"Missing prototype workspace shell: {shell_name}"
        assert f'workspace_id == "{workspace_id}"' in text, f"Missing route for workspace id: {workspace_id}"
        assert f"self.central_stack.setCurrentWidget(self.{workspace_id}_workspace)" in text


def test_ep_prototype_02_navigation_returns_to_home():
    class_node = _main_window_class()
    go_home = _method(class_node, "_go_home")
    source = ast.get_source_segment(_read(MAIN_WINDOW_PATH), go_home) or ""
    assert "self.central_stack.setCurrentWidget(self.home_page)" in source
    assert "self.home_page.refresh()" in source


def test_ep_prototype_02_shell_keeps_business_crud_out_of_workspace_selection():
    class_node = _main_window_class()
    method = _method(class_node, "_on_workspace_selected")
    source = ast.get_source_segment(_read(MAIN_WINDOW_PATH), method) or ""
    forbidden_operations = ("create_student", "update_student", "delete_student", "create_class", "delete_class")
    assert not any(operation in source for operation in forbidden_operations), (
        "Application-shell workspace routing must not own business CRUD operations"
    )
