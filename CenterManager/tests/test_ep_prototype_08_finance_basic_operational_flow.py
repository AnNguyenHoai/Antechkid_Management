"""Source-driven regression contract for EP-PROTOTYPE-08."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "centermanager" / "ui" / "finance_workspace"
SHELL = UI / "finance_workspace_shell.py"
DASHBOARD = UI / "finance_dashboard_page.py"


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


def test_ep_prototype_08_finance_shell_owns_basic_navigation():
    source = _read(SHELL)
    cls = _class_node(source, "FinanceWorkspaceShell")
    setup = _method_node(cls, "_setup_ui")
    navigate = _method_node(cls, "navigate_to")
    setup_source = ast.unparse(setup)
    navigate_source = ast.unparse(navigate)

    assert "FinanceDashboardPage" in setup_source
    assert "IncomeListPage" in setup_source
    assert "ExpenseListPage" in setup_source
    assert "navigate_to" in source
    assert '"income"' in navigate_source
    assert '"expense"' in navigate_source
    assert '"dashboard"' in navigate_source


def test_ep_prototype_08_finance_access_is_permission_gated():
    source = _read(SHELL)
    cls = _class_node(source, "FinanceWorkspaceShell")
    access = _method_node(cls, "_has_finance_access")
    navigate = _method_node(cls, "navigate_to")

    access_source = ast.unparse(access)
    navigate_source = ast.unparse(navigate)

    assert "finance.view" in access_source
    assert "_has_finance_access" in navigate_source
    assert "if not self._authorized" in navigate_source


def test_ep_prototype_08_dashboard_exposes_finance_summary():
    source = _read(DASHBOARD)
    cls = _class_node(source, "FinanceDashboardPage")
    refresh = _method_node(cls, "refresh")
    kpis = _method_node(cls, "_update_kpis")
    refresh_source = ast.unparse(refresh)
    kpis_source = ast.unparse(kpis)

    assert "get_dashboard_data" in refresh_source
    assert "revenue_by_method_month" in refresh_source
    assert "expense_by_method_month" in refresh_source
    assert "revenue_today" in kpis_source
    assert "revenue_month" in kpis_source
    assert "expense_today" in kpis_source
    assert "expense_month" in kpis_source
    assert "net_cash_flow" in kpis_source


def test_ep_prototype_08_does_not_introduce_duplicate_finance_layers():
    combined = "\n".join((_read(SHELL), _read(DASHBOARD)))
    for name in (
        "FinanceWorkspaceRouter",
        "FinanceWorkspaceService",
        "FinanceWorkspaceRepository",
        "AccountingEngine",
    ):
        assert name not in combined
