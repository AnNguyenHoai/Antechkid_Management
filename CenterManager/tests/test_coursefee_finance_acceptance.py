"""FIN-01..04: financial correctness, idempotent posting and voucher retry.

Synthetic database/files only: these tests never access CenterManager production.
"""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.core.current_user import CurrentUserContext
from centermanager.models.expense import Expense
from centermanager.models.income import Income
from centermanager.services.income_service import IncomeValidationError
from centermanager.services.expense_service import ExpenseValidationError
from centermanager.services.finance_attachment_service import FinanceAttachmentService
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider
from centermanager.ui.finance_workspace.voucher_attachment_widget import VoucherAttachmentWidget
from tests.test_fin_expense_funding_source import expense_env, _create
from tests.test_finance_f28_historical_income_edit import history, records


def test_exp01_reimbursed_personal_expense_cannot_be_reverted_by_edit(expense_env):
    factory, service = expense_env
    expense = _create(service, "PERSONAL", day=date(2026, 10, 5))
    service.reimburse_expense(expense.id, wallet="BANK", reimbursement_date=date(2026, 10, 15))
    with pytest.raises(ExpenseValidationError, match="cannot be made Pending"):
        service.update_expense(
            expense.id, payment_method="PERSONAL", status="Pending",
        )
    with factory() as db:
        current = db.get(Expense, expense.id)
        assert current.status == "Completed"
        assert current.payment_method == "BANK"
        assert current.payment_date == date(2026, 10, 15)


def test_fin03_expense_save_retry_reuses_one_ledger_row(expense_env):
    factory, service = expense_env
    payload = dict(
        category="Office Supply", description="Receipt paper", amount=150000,
        payment_method="BANK", payment_date=date(2026, 10, 10),
        paid_by="Manager", idempotency_key="expense:retry-1",
    )
    first = service.create_expense(**payload)
    again = service.create_expense(**payload)
    assert first.id == again.id
    with factory() as db:
        assert db.query(Expense).count() == 1
    with pytest.raises(ExpenseValidationError, match="different details"):
        service.create_expense(**{**payload, "amount": 250000})


def test_fin03_income_save_retry_reuses_one_ledger_row(history):
    factory, _students, _classes, service, _period = history
    actor = SimpleNamespace(
        id=1, username="finance", full_name="Finance",
        is_active=True, is_admin=False,
        role=SimpleNamespace(name="FINANCE"),
        permissions={"finance.income.create", "finance.view"},
    )
    payload = dict(
        amount=120000, income_type="Other", payment_method="CASH",
        payment_date=date(2026, 10, 20), payment_period=None,
        received_by="Finance", note="Synthetic income",
        idempotency_key="income:retry-1",
    )
    with CurrentUserContext(actor):
        first = service.create_income(**payload)
        again = service.create_income(**payload)
        assert first.id == again.id
        with pytest.raises(IncomeValidationError, match="different details"):
            service.create_income(**{**payload, "amount": 240000})
    with factory() as db:
        assert db.query(Income).count() == 1


def test_fin04_duplicate_voucher_retry_keeps_single_row_and_git_mirror(expense_env, tmp_path):
    factory, service = expense_env
    expense = _create(service, "BANK")
    runtime_root = tmp_path / "voucher-runtime"
    root = runtime_root / "Attachment"
    voucher = tmp_path / "expense.jpg"
    voucher.write_bytes(bytes([255, 216, 255, 224]) + b"synthetic-jpeg-receipt")
    attachments = FinanceAttachmentService(factory, root)
    first = attachments.add_attachment("EXPENSE", expense.id, voucher)
    replay = attachments.add_attachment("EXPENSE", expense.id, voucher)
    assert first.id == replay.id
    assert attachments.count_for("EXPENSE", [expense.id])[expense.id] == 1
    assert attachments.resolve_path(first).read_bytes() == voucher.read_bytes()

    # The same path is mirrored by GitSynchronizationProvider on Finish Editing.
    provider = object.__new__(GitSynchronizationProvider)
    provider._repo_path = runtime_root / "repository"
    assert provider._sync_finance_attachments_to_repository() == 1
    assert provider._sync_finance_attachments_to_repository() == 0
    published = provider._repo_path / "Attachments" / first.stored_path
    assert published.read_bytes() == voucher.read_bytes()
    # Simulate another workstation with only Git's published copy available.
    (root / first.stored_path).unlink()
    assert attachments.resolve_path(first) == published


def test_fin04_failed_pending_upload_is_retained_for_retry(qtbot, tmp_path):
    failed = {"first": True}
    class FakeAttachments:
        MAX_FILES_PER_RECORD = 5
        def list_attachments(self, kind, entity_id):
            return []
        def add_attachment(self, kind, entity_id, path, original_filename=None):
            if failed["first"]:
                failed["first"] = False
                raise RuntimeError("synthetic temporary error")
    widget = VoucherAttachmentWidget(FakeAttachments(), "EXPENSE")
    qtbot.addWidget(widget)
    path = str(tmp_path / "pending.jpg")
    widget._pending = [(path, "pending.jpg")]
    assert len(widget.commit_pending(77)) == 1
    assert widget._pending == [(path, "pending.jpg")]
    assert widget.commit_pending(77) == []
    assert widget._pending == []


def test_coursefee_fin03_migration_and_ui_command_keys_exist():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations/versions/cf26a001_coursefee_finance_submission_keys.py").read_text(encoding="utf-8")
    assert 'revision = "cf26a001"' in migration
    assert 'down_revision = "1e10a045"' in migration
    assert '"idempotency_key"' in migration
    assert "unique=True" in migration
    for filename in ("income_form_dialog.py", "expense_form_dialog.py"):
        src = (root / "src/centermanager/ui/finance_workspace" / filename).read_text(encoding="utf-8")
        assert "idempotency_key=self._submission_key" in src
    widget_src = (root / "src/centermanager/ui/finance_workspace/voucher_attachment_widget.py").read_text(encoding="utf-8")
    assert "self._pending = failed" in widget_src


def test_fin04_missing_committed_voucher_fails_closed(expense_env, tmp_path):
    factory, service = expense_env
    expense = _create(service, "BANK")
    root = tmp_path / "isolated-runtime" / "Attachment"
    voucher = tmp_path / "missing.jpg"
    voucher.write_bytes(bytes([255, 216, 255, 224]) + b"synthetic-jpeg")
    attachments = FinanceAttachmentService(factory, root)
    item = attachments.add_attachment("EXPENSE", expense.id, voucher)
    (root / item.stored_path).unlink()
    with pytest.raises(Exception, match="content is missing"):
        attachments.add_attachment("EXPENSE", expense.id, voucher)
    with factory() as db:
        from centermanager.models.finance_attachment import FinanceAttachment
        assert db.query(FinanceAttachment).count() == 1


def test_coursefee_income_ui_does_not_import_monthly_tuition():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "src/centermanager/services/income_service.py",
        "src/centermanager/ui/finance_workspace/income_form_dialog.py",
        "src/centermanager/services/expense_service.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "monthly_tuition" not in source.lower()
        assert "MonthlyTuition" not in source
        assert "TUITION_MONTH:" not in source
        assert "TUITION_QUARTER:" not in source


def test_coursefee_recovery_finance_has_no_monthly_tuition_reader():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "src/centermanager/platform/recovery_finance_compare.py",
        "src/centermanager/platform/recovery_business_compare.py",
    ):
        source = (root / relative).read_text(encoding="utf-8")
        assert "monthly_tuition" not in source.lower()
        assert "MonthlyTuition" not in source
