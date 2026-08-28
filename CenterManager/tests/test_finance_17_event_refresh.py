from pathlib import Path

def test_finance_event_contract_exists():
    source = Path("src/centermanager/events/finance_events.py").read_text(encoding="utf-8")
    assert "class FinanceDataChanged(Event)" in source
    assert "entity: str" in source
    assert "action: str" in source

def test_income_publishes_after_all_mutations():
    source = Path("src/centermanager/services/income_service.py").read_text(encoding="utf-8")
    assert '"created", income.id' in source
    assert '"updated", income.id' in source
    assert '"deleted", income_id' in source

def test_expense_publishes_after_all_mutations():
    source = Path("src/centermanager/services/expense_service.py").read_text(encoding="utf-8")
    assert 'self._publish_finance_change("created", expense.id)' in source
    assert 'self._publish_finance_change("updated", expense.id)' in source
    assert 'self._publish_finance_change("deleted", expense.id)' in source

def test_finance_shell_registers_and_refreshes():
    source = Path("src/centermanager/ui/finance_workspace/finance_workspace_shell.py").read_text(encoding="utf-8")
    assert "self._event_bus.register(FinanceDataChanged" in source
    assert "self.income_page.refresh()" in source
    assert "self.expense_page.refresh()" in source
    assert "self.outstanding_page.refresh()" in source
    assert "self.dashboard_page.refresh()" in source

def test_app_wires_single_event_bus_to_finance_services():
    source = Path("src/centermanager/app.py").read_text(encoding="utf-8")
    assert source.count("event_bus=event_bus") >= 2

def test_main_window_passes_event_bus_to_finance_workspace():
    source = Path("src/centermanager/ui/main_window.py").read_text(encoding="utf-8")
    assert "event_bus=self._event_bus" in source
