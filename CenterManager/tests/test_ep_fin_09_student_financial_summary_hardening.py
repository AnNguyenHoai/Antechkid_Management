from pathlib import Path


ROOT = Path("src/centermanager")
WIDGET = ROOT / "ui/student_workspace/student_financial_widget.py"
INCOME_REPOSITORY = ROOT / "repositories/income_repository.py"


def _widget_source() -> str:
    return WIDGET.read_text(encoding="utf-8")


def test_student_financial_uses_one_canonical_finance_period_context():
    source = _widget_source()
    assert "FinancePeriodService" in source
    assert "get_active_period" in source
    assert "get_period_bounds" in source
    assert "finance_period_start=period_start" in source
    assert "get_student_summary" in source
    assert "period_start=period_start" in source
    assert "on_date=target_date" in source


def test_payment_history_is_active_newest_first_and_not_magic_limited():
    source = _widget_source()
    assert "status=Income.STATUS_ACTIVE" in source
    assert 'sort_by="payment_date"' in source
    assert "ascending=False" in source
    assert "per_page=1000" not in source
    assert "per_page=total" in source


def test_payment_history_hides_soft_deleted_records_at_repository_boundary():
    source = INCOME_REPOSITORY.read_text(encoding="utf-8")
    assert "Income.deleted_at.is_(None)" in source
    assert "status=Income.STATUS_ACTIVE" in source


def test_student_financial_remains_read_only():
    source = _widget_source()
    forbidden_mutations = (
        "self._income_service.create_income(",
        "self._income_service.update_income(",
        "self._income_service.void_income(",
        "self._income_service.delete_income(",
    )
    for mutation in forbidden_mutations:
        assert mutation not in source


def test_student_financial_keeps_open_finance_navigation():
    source = _widget_source()
    assert "open_finance_clicked = Signal()" in source
    assert "self.open_finance_clicked.emit" in source
    assert 'has_permission("finance.view")' in source


def test_per_class_financial_status_is_rendered_not_documented_only():
    source = _widget_source()
    assert "detail.tuition_configured" in source
    assert "status_text = detail.status" in source
    assert 'status_text = "Chưa cấu hình"' in source
    assert "self.detail_table.setItem(row, 4, QTableWidgetItem(status_text))" in source


def test_student_financial_period_can_be_supplied_by_composition_root():
    source = _widget_source()
    assert "def set_finance_period(" in source
    assert "self._requested_period_start = period_start" in source
    assert "self._requested_on_date = on_date" in source
