"""Source-driven manual UAT execution contract for EP-PROTOTYPE-13."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MAIN_WINDOW = ROOT / "src" / "centermanager" / "ui" / "main_window.py"
HOME = ROOT / "src" / "centermanager" / "ui" / "home" / "home_page.py"
STUDENT_SHELL = ROOT / "src" / "centermanager" / "ui" / "student_workspace" / "student_workspace_shell.py"
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


def test_ep_prototype_13_manual_uat_contract_is_explicit():
    doc = _read(DOCS / "EP-PROTOTYPE-13_UAT_EXECUTION.md")
    for phrase in (
        "Manual checklist",
        "Application shell",
        "Student flow",
        "Class and session flow",
        "Finance flow",
        "Regression",
        "Defect handling",
        "separate fix PR",
    ):
        assert phrase in doc


def test_ep_prototype_13_application_router_remains_single():
    main_source = _read(MAIN_WINDOW)
    main_cls = _class_node(main_source, "MainWindow")
    selected = ast.unparse(_method_node(main_cls, "_on_workspace_selected"))
    assert "central_stack.setCurrentWidget" in selected
    for workspace_id in ("student", "teacher", "class", "finance", "employee", "admin"):
        assert workspace_id in selected


def test_ep_prototype_13_operational_surfaces_remain_reachable_in_source():
    home_cls = _class_node(_read(HOME), "HomePage")
    assert "workspace_selected.emit" in ast.unparse(_method_node(home_cls, "_on_workspace_clicked"))

    student_cls = _class_node(_read(STUDENT_SHELL), "StudentWorkspaceShell")
    student_setup = ast.unparse(_method_node(student_cls, "_setup_ui"))
    assert "StudentDetailPage" in student_setup

    class_cls = _class_node(_read(CLASS_DETAIL), "ClassDetailPage")
    assert "ClassScheduleWidget" in ast.unparse(_method_node(class_cls, "_create_overview_tab"))

    session_cls = _class_node(_read(SESSION_DETAIL), "SessionDetailDialog")
    session_setup = ast.unparse(_method_node(session_cls, "_setup_ui"))
    assert "SessionAttendanceWidget" in session_setup
    assert "Teaching Overview" in session_setup

    finance_cls = _class_node(_read(FINANCE_SHELL), "FinanceWorkspaceShell")
    finance_setup = ast.unparse(_method_node(finance_cls, "_setup_ui"))
    for surface in ("Dashboard", "Income", "Expense", "Outstanding"):
        assert surface in finance_setup
