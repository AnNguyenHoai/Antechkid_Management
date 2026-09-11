from pathlib import Path

def read(rel):
    return Path(rel).read_text(encoding="utf-8")

def test_dashboard_declares_finance_navigation_signals():
    source = read("src/centermanager/ui/finance_workspace/finance_dashboard_page.py")
    assert "go_to_income = Signal()" in source
    assert "go_to_expense = Signal()" in source
    assert "go_to_outstanding = Signal()" in source

def test_dashboard_recent_rows_open_records():
    source = read("src/centermanager/ui/finance_workspace/finance_dashboard_page.py")
    assert "income_selected = Signal(int)" in source
    assert "expense_selected = Signal(int)" in source
    assert "row_double_clicked.connect(self._on_income_row_double_clicked)" in source
    assert "row_double_clicked.connect(self._on_expense_row_double_clicked)" in source

def test_finance_shell_routes_dashboard_workflow():
    source = read("src/centermanager/ui/finance_workspace/finance_workspace_shell.py")
    assert 'self.navigate_to("income")' in source
    assert 'self.navigate_to("expense")' in source
    assert 'self.navigate_to("outstanding")' in source
    assert "self.dashboard_page.income_selected.connect" in source
    assert "self.dashboard_page.expense_selected.connect" in source

def test_outstanding_can_open_student_workspace():
    shell = read("src/centermanager/ui/finance_workspace/finance_workspace_shell.py")
    main = read("src/centermanager/ui/main_window.py")
    assert "student_selected = Signal(int)" in shell
    assert "self.outstanding_page.student_selected.connect(self.student_selected.emit)" in shell
    assert "self.finance_workspace.student_selected.connect(self._show_student_from_finance)" in main
    assert "self.student_workspace.show_student(student_id)" in main

def test_navigation_uses_existing_detail_dialogs():
    source = read("src/centermanager/ui/finance_workspace/finance_workspace_shell.py")
    assert "self.income_page._show_detail_dialog(income_id)" in source
    assert "self.expense_page._show_detail_dialog(expense_id)" in source
