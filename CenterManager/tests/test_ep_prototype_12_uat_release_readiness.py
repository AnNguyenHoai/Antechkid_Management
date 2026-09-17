"""Source-driven release-readiness contract for EP-PROTOTYPE-12."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
TESTS = ROOT / "tests"
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
    return next(child for child in node.body if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == name)


def test_ep_prototype_12_prior_prototype_regression_contracts_are_present():
    for number in range(1, 12):
        assert list(DOCS.glob(f"EP-PROTOTYPE-{number:02d}_*.md")), f"missing EP-PROTOTYPE-{number:02d} documentation"
        assert list(TESTS.glob(f"test_ep_prototype_{number:02d}_*.py")), f"missing EP-PROTOTYPE-{number:02d} regression test"


def test_ep_prototype_12_single_application_router_and_existing_workspace_shells():
    combined = "\n".join(_read(path) for path in (MAIN_WINDOW, HOME, STUDENT_SHELL, CLASS_DETAIL, SESSION_DETAIL, FINANCE_SHELL))
    for name in ("ApplicationRouter", "DashboardRouter", "WorkspaceRouter", "HomeDashboardRouter"):
        assert name not in combined
    main_cls = _class_node(_read(MAIN_WINDOW), "MainWindow")
    selected = ast.unparse(_method_node(main_cls, "_on_workspace_selected"))
    for workspace_id in ("student", "teacher", "class", "finance", "employee", "admin"):
        assert workspace_id in selected
    assert "central_stack.setCurrentWidget" in selected


def test_ep_prototype_12_golden_flow_surfaces_remain_composed():
    home_cls = _class_node(_read(HOME), "HomePage")
    assert "workspace_selected.emit" in ast.unparse(_method_node(home_cls, "_on_workspace_clicked"))
    student_cls = _class_node(_read(STUDENT_SHELL), "StudentWorkspaceShell")
    student_setup = ast.unparse(_method_node(student_cls, "_setup_ui"))
    assert "StudentDetailPage" in student_setup
    for dependency in ("timeline_service", "assessment_service", "attendance_service", "enrollment_service"):
        assert dependency in student_setup
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


def test_ep_prototype_12_uat_is_manual_not_a_second_runtime_path():
    doc = _read(DOCS / "EP-PROTOTYPE-12_UAT_RELEASE_READINESS.md")
    assert "Manual UAT checklist" in doc
    assert "CI remains source-driven" in doc
    assert "No new routing framework" in doc
    assert "No new persistence layer" in doc
    assert "production defect" in doc
