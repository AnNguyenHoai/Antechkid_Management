"""FIN-01..04: financial correctness, idempotent posting and voucher retry.

Synthetic database/files only: these tests never access CenterManager production.
"""
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.core.current_user import CurrentUserContext
from centermanager.models.expense import Expense
from centermanager.models.income import Income
from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.expense_service import ExpenseValidationError
from centermanager.services.finance_attachment_service import FinanceAttachmentService
from centermanager.platform.synchronization.git_synchronization_provider import GitSynchronizationProvider
from centermanager.ui.finance_workspace.voucher_attachment_widget import VoucherAttachmentWidget
from tests.test_fin_expense_funding_source import expense_env, _create
from tests.test_finance_f28_historical_income_edit import history, records


@pytest.mark.parametrize("accrued,settled,cash,credit,allowed", [
    (700000, 0, 600000, 100000, True),
    (700000, 0, 600000, 300000, False),
    (700000, 200000, 400000, 100000, True),
    (700000, 200000, 400000, 200000, False),
    (700000, 0, 700000, 1, False),
    (700000, 0, 900000, 1, False),
])
def test_fin01_credit_cannot_over_settle_earned_tuition(
    accrued, settled, cash, credit, allowed
):
    args = dict(accrued=accrued, settled=settled, cash=cash, credit=credit)
    if allowed:
        IncomeService._validate_payment_time_credit_capacity(**args)
    else:
        with pytest.raises(IncomeValidationError, match="exceeds earned"):
            IncomeService._validate_payment_time_credit_capacity(**args)


def test_fin02_nonquoted_income_cannot_become_monthly_quarterly_quote_by_edit(history):
    factory, _students, _classes, service, _period = history
    income_id, _ = records(history, income_type="Tuition")
    actor = SimpleNamespace(
        id=1, username="finance", full_name="Finance",
        is_active=True, is_admin=False,
        role=SimpleNamespace(name="FINANCE"),
        permissions={"finance.view", "finance.income.update"},
    )
    with CurrentUserContext(actor):
        for quoted in ("TUITION_MONTH:2026-10-01", "TUITION_QUARTER:2026-10-01"):
            with pytest.raises(IncomeValidationError, match="verified quote"):
                service.update_income(income_id, payment_period=quoted)
    with factory() as db:
        assert db.get(Income, income_id).payment_period == ""


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


def test_fin03_migration_and_ui_command_keys_exist():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations/versions/1e10a048_finance_submission_keys.py").read_text()
    assert 'down_revision = "1e10a047"' in migration
    assert '"idempotency_key"' in migration
    assert "unique=True" in migration
    for filename in ("income_form_dialog.py", "expense_form_dialog.py"):
        src = (root / "src/centermanager/ui/finance_workspace" / filename).read_text()
        assert "idempotency_key=self._submission_key" in src
    widget_src = (root / "src/centermanager/ui/finance_workspace/voucher_attachment_widget.py").read_text()
    assert "self._pending = failed" in widget_src
