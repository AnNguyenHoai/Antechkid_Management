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


def test_refund_adapter_delegates_preview_without_mutation():
    service = TuitionRefundService.__new__(TuitionRefundService)
    service._adjustments = MagicMock()
    service._adjustments.preview.return_value = {
        "enrollment_id": 11,
        "refundable_amount": Decimal("1250000.00"),
    }

    result = service.preview(11)

    assert result["refundable_amount"] == Decimal("1250000.00")
    service._adjustments.preview.assert_called_once_with(11, as_of_date=None)


def test_refund_compatibility_adapter_cannot_bypass_adjustment_ledger():
    root = Path(__file__).resolve().parents[1]
    adapter = (root / "src/centermanager/services/tuition_refund.py").read_text(encoding="utf-8")
    implementation = (root / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")

    assert "TuitionAdjustmentService(" in adapter
    assert "self._adjustments.refund(" in adapter
    assert "linked_income_id" in adapter
    assert "Income(" not in adapter

    assert "amount=-float(value)" in implementation
    assert 'income_type="Tuition"' in implementation
    assert 'payment_period="REFUND"' in implementation
    assert "sum_active_tuition_for_enrollment(" in implementation
    assert "FinanceLedgerGuard.ensure_date_mutable" in implementation
    assert "models.finance_period" not in implementation
    assert "FinancePeriod" not in implementation


def test_refund_guards_origin_prepaid_period_audit_and_idempotency_contracts():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")

    assert "Adjustment amount must be greater than 0" in source
    assert "exceeds refundable tuition" in source
    assert "prepaid_only" in source
    assert "exceeds available prepaid credit" in source
    assert "TuitionAccrualService.calculate_from_records" in source
    assert "FinanceLedgerGuard.ensure_date_mutable" in source
    assert 'action="TUITION_REFUND"' in source
    assert 'module="tuition"' in source
    assert "Adjustment reason is required" in source
    assert '@require_permission("finance.income.create")' in source
    assert "Idempotency key is required" in source
    assert "get_by_idempotency_key" in source


def test_origin_payment_is_structurally_linked_and_capped():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/tuition_adjustment_service.py").read_text(encoding="utf-8")

    assert 'origin.income_type != "Tuition"' in source
    assert "origin.status != Income.STATUS_ACTIVE" in source
    assert "float(origin.amount) <= 0" in source
    assert "origin.enrollment_id != enrollment_id" in source
    assert "sum_refunds_for_origin(origin_income_id)" in source
    assert "exceeds origin remaining refundable" in source
    assert "origin_income_id=origin_income_id" in source
    assert "linked_income_id=income.id" in source
