from pathlib import Path

from centermanager.events.event_bus import EventBus
from centermanager.events.finance_events import FinanceDataChanged
from centermanager.ui.finance_workspace.finance_dashboard_page import FinanceDashboardPage
from centermanager.ui.finance_workspace.finance_workspace_shell import FinanceWorkspaceShell


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_real_transaction_drilldown_signals():
    assert hasattr(FinanceDashboardPage, "income_selected")
    assert hasattr(FinanceDashboardPage, "expense_selected")


def test_finance_shell_exposes_student_navigation_boundary():
    assert hasattr(FinanceWorkspaceShell, "student_selected")


def test_finance_event_bus_dispatches_real_finance_change():
    bus = EventBus()
    seen = []
    bus.register(FinanceDataChanged, seen.append)
    event = FinanceDataChanged(entity="expense", action="created", entity_id=42)
    bus.publish(event)
    assert seen == [event]


def test_expense_service_contains_real_event_publication_not_comment_contract():
    source = (ROOT / "src" / "centermanager" / "services" / "expense_service.py").read_text(encoding="utf-8")
    assert "def _publish_finance_change" in source
    assert 'self._publish_finance_change("created", expense_id)' in source
    assert 'self._publish_finance_change("updated", expense.id)' in source
    assert 'self._publish_finance_change("deleted", expense_id)' in source


def test_finance_lists_have_real_sort_handlers_and_safe_notification_fallback():
    income = (ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "income_list_page.py").read_text(encoding="utf-8")
    expense = (ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "expense_list_page.py").read_text(encoding="utf-8")
    assert "def _on_sort" in income and "self._incomes.sort" in income

    # Income still sorts the already-loaded list locally. EP-FIN-11 moved
    # Expense to server-side sorting so the handler must update the requested
    # sort and reload the page instead of sorting the current page in memory.
    assert "def _on_sort" in expense
    assert "self._sort_by, self._sort_ascending, self._current_page = key, ascending, 1" in expense
    assert "sort_by=self._sort_by" in expense
    assert "ascending=self._sort_ascending" in expense
    assert "self._expenses.sort" not in expense

    assert "def _notify" in income and "def _notify" in expense


def test_finance_shell_registers_real_event_refresh():
    source = (ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "finance_workspace_shell.py").read_text(encoding="utf-8")
    assert "self._event_bus.register(FinanceDataChanged, self._on_finance_data_changed)" in source
    assert "def _on_finance_data_changed" in source
