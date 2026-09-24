from pathlib import Path
import ast

ROOT = Path("src/centermanager")


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_ep_fin_11_changed_python_sources_parse():
    files = [
        "repositories/expense_repository.py",
        "services/expense_service.py",
        "services/finance_dashboard_service.py",
        "services/financial_settlement_service.py",
        "ui/finance_workspace/expense_list_page.py",
        "ui/finance_workspace/finance_period_config_dialog.py",
        "ui/finance_workspace/finance_workspace_shell.py",
    ]
    for relative in files:
        ast.parse(_source(relative), filename=relative)


def test_expense_repository_has_server_side_query_contract():
    source = _source("repositories/expense_repository.py")
    assert "def _filtered_query(" in source
    assert "SORT_COLUMNS" in source
    assert "finance_period_start" in source
    assert "sort_by" in source
    assert "ascending" in source
    assert ".offset(" in source and ".limit(" in source
    assert 'REALIZED_STATUSES = ("Completed", "Paid")' in source


def test_expense_service_exposes_full_filtered_export_and_paging():
    source = _source("services/expense_service.py")
    assert "def export_expenses_csv(" in source
    assert "finance_period_start" in source
    assert "sort_by" in source
    assert "repo.count_active(**kwargs)" in source
    assert "limit=max(total, 1)" in source
    assert 'encoding="utf-8-sig"' in source


def test_expense_workspace_no_longer_loads_first_1000_and_slices_locally():
    source = _source("ui/finance_workspace/expense_list_page.py")
    assert "per_page=1000" not in source
    assert "page_requested.connect(self._on_page_requested)" in source
    assert "set_server_data(" in source
    assert "finance_period_start=self._period_start" in source
    assert "export_expenses_csv(" in source
    assert "self._sort_by" in source


def test_pending_expense_is_not_realized_in_dashboard_or_settlement():
    dashboard = _source("services/finance_dashboard_service.py")
    settlement = _source("services/financial_settlement_service.py")
    assert dashboard.count("realized_only=True") >= 3
    assert "finance_period_start=resolved_period_start" in dashboard
    assert "realized_only=True" in settlement


def test_finance_period_configuration_ui_uses_existing_service_contract():
    dialog = _source("ui/finance_workspace/finance_period_config_dialog.py")
    shell = _source("ui/finance_workspace/finance_workspace_shell.py")
    assert "list_period_configurations()" in dialog
    assert "self._service.configure(" in dialog
    assert "self._service.deactivate(" in dialog
    assert "FinancePeriodConfigDialog" in shell
    assert 'user.has_permission("finance.period.manage")' in shell
    assert "ensure_write()" in shell


def test_finance_event_refresh_still_updates_all_shared_period_pages():
    source = _source("ui/finance_workspace/finance_workspace_shell.py")
    assert "self._event_bus.register(FinanceDataChanged" in source
    assert "self._refresh_pages([" in source
    for page in ("dashboard_page", "income_page", "expense_page", "outstanding_page", "settlement_page"):
        assert f"self.{page}," in source
    assert "def _period_context" in source
    assert '"target_date": target_date' in source
    assert '"period_start": period_start' in source
    assert '"period_end": period_end' in source
    assert '"period_configured": configured' in source
    assert '"period_closed": closed' in source
    assert "page.refresh(**context)" in source


def test_student_financial_remains_read_only():
    source = _source("ui/student_workspace/financial_widget.py")
    assert "Collect Tuition" not in source
    assert "CollectTuitionDialog" not in source
    assert ".create_income(" not in source
    assert ".update_income(" not in source
    assert ".delete_income(" not in source
