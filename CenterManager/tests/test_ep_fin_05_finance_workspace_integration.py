from pathlib import Path


UI_ROOT = Path("src/centermanager/ui")
FINANCE_ROOT = UI_ROOT / "finance_workspace"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_finance_workspace_owns_single_canonical_period_selector():
    shell = _source(FINANCE_ROOT / "finance_workspace_shell.py")
    dashboard = _source(FINANCE_ROOT / "finance_dashboard_page.py")
    settlement = _source(FINANCE_ROOT / "financial_settlement_page.py")

    assert "self.period_combo = QComboBox()" in shell
    assert "self.month_combo" not in shell
    assert "self.year_combo" not in shell
    assert "list_resolved_periods" in shell
    assert "def _resolve_shared_period" in shell
    assert "_target_date_for_period" in shell

    # Dashboard and Settlement consume the workspace context instead of owning
    # independent selectors that can drift to a different FinancePeriod.
    for page in (dashboard, settlement):
        assert "self.month_combo" not in page
        assert "self.year_combo" not in page


def test_shell_propagates_same_canonical_period_context_to_finance_pages():
    shell = _source(FINANCE_ROOT / "finance_workspace_shell.py")

    assert "def _period_context" in shell
    assert '"target_date": target_date' in shell
    assert '"period_start": period_start' in shell
    assert '"period_end": period_end' in shell
    assert '"period_configured": configured' in shell
    assert '"period_closed": closed' in shell
    assert "page.refresh(**context)" in shell
    assert "self.dashboard_page" in shell
    assert "self.income_page" in shell
    assert "self.expense_page" in shell
    assert "self.outstanding_page" in shell
    assert "self.settlement_page" in shell


def test_income_expense_and_outstanding_are_scoped_to_shared_period():
    income = _source(FINANCE_ROOT / "income_list_page.py")
    expense = _source(FINANCE_ROOT / "expense_list_page.py")
    outstanding = _source(FINANCE_ROOT / "outstanding_list_page.py")

    assert "finance_period_start=self._period_start" in income
    assert "max(user_from, self._period_start)" in income
    assert "min(user_to, self._period_end)" in income

    assert "max(user_from, self._period_start)" in expense
    assert "min(user_to, self._period_end)" in expense
    # EP-FIN-11 builds one server-filter dictionary and forwards it to the
    # paged Expense query. Keep this contract instead of requiring the old
    # explicit date_from=/date_to= call-site spelling.
    assert '"date_from": date_from' in expense
    assert '"date_to": date_to' in expense
    assert "kwargs = self._filter_kwargs()" in expense
    assert "**kwargs," in expense

    assert "period_start=self._period_start" in outstanding
    assert "on_date=self._target_date" in outstanding


def test_settlement_uses_workspace_target_date_for_preview_and_writes():
    settlement = _source(FINANCE_ROOT / "financial_settlement_page.py")

    assert "QComboBox" not in settlement
    assert "self._target_date = get_clock().today()" in settlement
    assert "self._target_date = target_date" in settlement
    assert "get_preview(target_date=self._target_date)" in settlement
    assert '"target_date": self._target_date' in settlement
    assert "Save Draft" in settlement
    assert "Confirm Settlement" in settlement


def test_student_workspace_finance_tab_is_read_only():
    student_finance = _source(UI_ROOT / "student_workspace" / "financial_widget.py")

    assert "Collect Tuition" not in student_finance
    assert "CollectTuitionDialog" not in student_finance
    assert "create_income(" not in student_finance
    assert "Finance → Income" in student_finance
    assert "Payment History" in student_finance
    assert "Total Paid" in student_finance
