from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
from datetime import date

from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.services.tuition_adjustment_service import TuitionAdjustmentService


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_migration_is_linear_and_creates_structured_adjustment_ledger():
    source = (_root() / "migrations/versions/1e10a037_tuition_adjustment_ledger.py").read_text(encoding="utf-8")
    assert 'revision = "1e10a037"' in source
    assert 'down_revision = "1e10a036"' in source
    assert '"tuition_adjustments"' in source
    assert '"origin_income_id"' in source
    assert '"origin_adjustment_id"' in source
    assert '"linked_income_id"' in source
    assert '"idempotency_key"' in source
    assert 'name="ck_tuition_adjustment_shape"' in source
    assert 'name="uq_tuition_adjustment_idempotency_key"' in source


def test_adjustment_model_has_explicit_cash_and_non_cash_kinds():
    assert TuitionAdjustment.KIND_REFUND == "REFUND"
    assert TuitionAdjustment.KIND_CREDIT == "CREDIT_ADJUSTMENT"
    table_text = str(TuitionAdjustment.__table__)
    assert "tuition_adjustments" in table_text


def test_repository_owns_locks_origin_caps_and_idempotency_lookup():
    source = (_root() / "src/centermanager/repositories/tuition_adjustment_repository.py").read_text(encoding="utf-8")
    assert "with_for_update()" in source
    assert "lock_enrollment" in source
    assert "lock_origin_income" in source
    assert "sum_refunds_for_origin" in source
    assert "get_by_idempotency_key" in source


def test_same_idempotency_key_is_bound_to_full_command_identity():
    existing = SimpleNamespace(
        kind="REFUND",
        enrollment_id=10,
        amount=Decimal("100.00"),
        adjustment_date=date(2026, 9, 25),
        origin_income_id=20,
        origin_adjustment_id=None,
        wallet="CASH",
        reason="Parent request",
    )
    command = dict(
        kind="REFUND",
        enrollment_id=10,
        amount=Decimal("100.00"),
        adjustment_date=date(2026, 9, 25),
        origin_income_id=20,
        origin_adjustment_id=None,
        wallet="CASH",
        reason="Parent request",
    )
    assert TuitionAdjustmentService._same_command(existing, **command)
    command["origin_income_id"] = 21
    assert not TuitionAdjustmentService._same_command(existing, **command)


def test_refund_is_cash_linked_but_credit_adjustment_has_no_income_or_wallet_movement():
    source = (_root() / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")
    refund_body = source.split("def refund(", 1)[1].split("def credit_adjustment(", 1)[0]
    credit_body = source.split("def credit_adjustment(", 1)[1]

    assert "Income(" in refund_body
    assert "amount=-float(value)" in refund_body
    assert "linked_income_id=income.id" in refund_body
    assert "sum_refunds_for_origin(origin_income_id)" in refund_body
    assert "with_for_update" not in refund_body

    assert "Income(" not in credit_body
    assert "linked_income_id=None" in credit_body
    assert "wallet=None" in credit_body
    assert '"wallet_movement": False' in credit_body


def test_non_cash_credit_projects_to_tuition_settlement_without_wallet_income():
    source = (_root() / "src/centermanager/repositories/income_repository.py").read_text(encoding="utf-8")
    assert "TuitionAdjustment.KIND_CREDIT" in source
    assert "non_cash_credit" in source
    assert "paid\n            + non_cash_credit" in source


def test_adjustments_publish_finance_events_and_keep_accounting_boundary():
    source = (_root() / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")
    assert "FinanceDataChanged(" in source
    assert 'entity="tuition_adjustment"' in source
    assert 'entity="income"' in source
    assert "FinanceLedgerGuard.ensure_date_mutable" in source
    assert "models.finance_period" not in source
    assert "FinancePeriod" not in source


def test_refund_never_mutates_historical_origin_income():
    source = (_root() / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")
    assert "origin.amount =" not in source
    assert "origin.status =" not in source
    assert "origin.deleted_at =" not in source
    assert "origin_income_id=origin_income_id" in source


def test_legacy_refund_api_routes_through_first_class_ledger():
    source = (_root() / "src/centermanager/services/tuition_refund.py").read_text(encoding="utf-8")
    assert "TuitionAdjustmentService(" in source
    assert "self._adjustments.refund(" in source
    assert "legacy-refund-" in source
    assert "Income(" not in source


def test_active_enrollment_ui_exposes_refund_and_non_cash_credit_actions():
    source = (_root() / "src/centermanager/ui/student_workspace/enrollment_widget.py").read_text(encoding="utf-8")
    assert 'Button("Refund tuition"' in source
    assert 'Button("Tuition credit"' in source
    assert "self._adjustment_service.preview(enrollment.id)" in source
    assert "self._adjustment_service.refund(" in source
    assert "self._adjustment_service.credit_adjustment(" in source
    assert 'idempotency_key=f"ui-refund-{uuid4()}"' in source
    assert 'idempotency_key=f"ui-credit-{uuid4()}"' in source
    assert '["CASH", "BANK"]' in source
