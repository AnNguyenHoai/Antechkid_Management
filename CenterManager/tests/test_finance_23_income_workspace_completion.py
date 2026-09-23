"""EP-FIN-06 static regression contracts.

These tests intentionally avoid importing PySide so architecture regressions are
caught in lightweight CI environments as well.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_income_model_has_explicit_void_lifecycle():
    source = _source("src/centermanager/models/income.py")
    assert 'STATUS_ACTIVE = "ACTIVE"' in source
    assert 'STATUS_VOIDED = "VOIDED"' in source
    assert "voided_at" in source
    assert "voided_by" in source
    assert "void_reason" in source


def test_income_repository_live_queries_only_return_active_records():
    source = _source("src/centermanager/repositories/income_repository.py")
    assert "status=Income.STATUS_ACTIVE" in source
    assert "def list_records" in source
    assert "def count_records" in source
    assert "sort_by" in source
    assert "ascending" in source


def test_income_service_has_audit_void_export_and_identity_safe_update():
    source = _source("src/centermanager/services/income_service.py")
    assert "def void_income" in source
    assert '"VOID"' in source
    assert "record_in_session" in source
    assert "Only ACTIVE income can be edited." in source
    assert "def export_incomes_csv" in source

    update_section = source.split("def update_income(", 1)[1].split(
        "def void_income(", 1
    )[0]
    assert "student_id:" not in update_section
    assert "class_id:" not in update_section
    assert "income_type:" not in update_section


def test_income_list_uses_real_server_pagination_and_shared_finance_period():
    source = _source(
        "src/centermanager/ui/finance_workspace/income_list_page.py"
    )
    assert "set_server_data" in source
    assert "page_requested.connect" in source
    assert "per_page=1000" not in source
    assert "per_page=10000" not in source
    assert "def _on_sort" in source
    assert "def _void_income" in source
    assert "def _export_csv" in source
    assert "finance_period_start" in source
    assert "self.period_combo = QComboBox()" not in source


def test_edit_dialog_locks_transaction_identity_and_updates_receiver():
    source = _source(
        "src/centermanager/ui/finance_workspace/income_form_dialog.py"
    )
    assert "def _lock_identity_fields" in source
    assert "self.source_combo.setEnabled(False)" in source
    assert "self.student_combo.setEnabled(False)" in source
    assert "self.class_combo.setEnabled(False)" in source
    assert "self.type_combo.setEnabled(False)" in source
    assert "received_by=received_by" in source


def test_student_finance_remains_read_only():
    source = _source(
        "src/centermanager/ui/student_workspace/student_financial_widget.py"
    )
    assert "CollectTuitionDialog" not in source
    assert "create_income(" not in source
    assert "update_income(" not in source
    assert "delete_income(" not in source
    assert "void_income(" not in source
    assert "Open Finance Workspace" in source
    assert "open_finance_clicked" in source


def test_income_lifecycle_migration_follows_finance_head():
    source = _source(
        "migrations/versions/1e10a022_income_lifecycle.py"
    )
    assert 'revision = "1e10a022"' in source
    assert 'down_revision = "1e10a021"' in source
    assert '"status"' in source
    assert '"voided_at"' in source
    assert '"void_reason"' in source