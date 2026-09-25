from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from centermanager.services.tuition_refund import (
    TuitionRefundService,
    TuitionRefundValidationError,
    _money,
)


def test_money_is_canonical_two_decimal_value():
    assert _money("100000.005") == Decimal("100000.01")
    assert _money(None) == Decimal("0.00")


def test_refund_reason_is_required_and_trimmed():
    with pytest.raises(TuitionRefundValidationError, match="Refund reason is required"):
        TuitionRefundService._reason("   ")
    assert TuitionRefundService._reason("  Parent request  ") == "Parent request"


def test_preview_returns_current_refundable_settlement_without_mutation():
    enrollment = MagicMock(id=11)
    enrollment_repo = MagicMock()
    enrollment_repo.get_by_id.return_value = enrollment
    income_repo = MagicMock()
    income_repo.sum_active_tuition_for_enrollment.return_value = Decimal("1250000")
    provider = MagicMock()
    provider.enrollments.return_value = enrollment_repo
    provider.incomes.return_value = income_repo
    session = MagicMock()
    session_factory = MagicMock()
    session_factory.return_value.__enter__.return_value = session

    service = TuitionRefundService(
        session_factory,
        repository_provider=provider,
        audit_service=MagicMock(),
    )
    result = service.preview(11)

    assert result["refundable_amount"] == Decimal("1250000.00")
    enrollment_repo.get_by_id.assert_called_once_with(11)
    income_repo.sum_active_tuition_for_enrollment.assert_called_once()


def test_refund_implementation_is_append_only_and_projects_to_tuition_and_wallet():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/tuition_refund.py").read_text(encoding="utf-8")

    # Dedicated workflow: normal IncomeService never creates negative amounts.
    assert 'REFUND_MARKER = "tuition_refund=true"' in source
    assert 'amount=-float(value)' in source
    assert 'income_type=self.REFUND_TYPE' in source
    assert 'payment_period="REFUND"' in source

    # Existing tuition settlement and Wallet V2 consume the same immutable row.
    assert "sum_active_tuition_for_enrollment(" in source
    assert "canonical_wallet_value" in source
    assert "finance_period_start=accounting_period_start" in source

    # Historical payment is only read/validated, never edited or voided.
    assert "origin = incomes.get_by_id(origin_income_id)" in source
    assert "origin_income_id" in source
    assert "origin.amount =" not in source
    assert "origin.status =" not in source
    assert "void_reason" not in source


def test_refund_guards_amount_prepaid_period_and_audit_contracts():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/tuition_refund.py").read_text(encoding="utf-8")

    assert "Refund amount must be greater than 0" in source
    assert "exceeds refundable tuition" in source
    assert "prepaid_only" in source
    assert "exceeds available prepaid credit" in source
    assert "TuitionAccrualService.calculate_from_records" in source
    assert "FinanceLedgerGuard.ensure_date_mutable" in source
    assert "models.finance_period" not in source
    assert "FinancePeriod" not in source
    assert 'action="TUITION_REFUND"' in source
    assert 'module="tuition"' in source
    assert "Refund reason is required" in source
    assert '@require_permission("finance.income.create")' in source


def test_origin_payment_must_be_positive_active_tuition_for_same_enrollment():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/tuition_refund.py").read_text(encoding="utf-8")

    assert 'origin.income_type != "Tuition"' in source
    assert "origin.status != Income.STATUS_ACTIVE" in source
    assert "float(origin.amount) <= 0" in source
    assert "origin.enrollment_id != enrollment_id" in source
    assert "Origin payment belongs to a different Enrollment" in source
