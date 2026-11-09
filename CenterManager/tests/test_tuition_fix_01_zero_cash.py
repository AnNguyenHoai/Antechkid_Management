"""TUITION-FIX-01: zero-price contracts and credit-only (zero cash) regression."""
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.services.enrollment_service import EnrollmentService
from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.ui.finance_workspace.income_form_dialog import IncomeFormDialog


def test_zero_course_price_is_configured_not_missing():
    free_class = SimpleNamespace(
        has_course_contract=True,
        course_fee=Decimal("0"),
        planned_sessions=24,
    )
    contract = EnrollmentService._snapshot_tuition_contract(
        free_class, enrolled_from_session=1, enrolled_until_session=None
    )
    assert contract["agreed_course_fee"] == Decimal("0")
    assert contract["unit_fee"] == Decimal("0")
    assert contract["discount_amount"] == Decimal("0")


def test_full_course_discount_is_zero_net_obligation():
    class_record = SimpleNamespace(
        has_course_contract=True,
        course_fee=Decimal("2400000"),
        planned_sessions=24,
    )
    contract = EnrollmentService._snapshot_tuition_contract(
        class_record,
        enrolled_from_session=1,
        enrolled_until_session=None,
        discount_type="PERCENT",
        discount_value=Decimal("100"),
        discount_source="MANUAL",
        discount_reason="Scholarship approved",
    )
    assert contract["agreed_course_fee"] == Decimal("2400000")
    assert contract["discount_amount"] == Decimal("2400000")
    assert contract["agreed_course_fee"] - contract["discount_amount"] == 0


@pytest.mark.parametrize("amount,is_edit,is_student,kind,checked,visible,expected", [
    (0, False, True, "Tuition", True, True, True),
    (0, False, True, "Tuition", False, True, False),
    (0, True, True, "Tuition", True, True, False),
    (0, False, False, "Other", True, True, False),
    (0, False, True, "Book", True, True, False),
    (-1, False, True, "Tuition", True, True, False),
    (0, False, True, "Tuition", True, False, False),
    (100, False, True, "Tuition", True, True, False),
])
def test_zero_cash_is_allowed_only_as_non_cash_tuition_adjustment(
    amount, is_edit, is_student, kind, checked, visible, expected,
):
    assert IncomeFormDialog._is_credit_only_request(
        amount=amount,
        is_edit=is_edit,
        is_student=is_student,
        income_type=kind,
        credit_checked=checked,
        credit_visible=visible,
    ) is expected


def test_regular_income_api_still_forbids_zero_or_negative_receipts():
    service = IncomeService.__new__(IncomeService)
    with pytest.raises(IncomeValidationError):
        service._validate_amount(0)
    with pytest.raises(IncomeValidationError):
        service._validate_amount(-1)
    assert service._validate_amount(123) == 123


def test_zero_cash_path_never_calls_income_creation_or_creates_wallet_entry():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    dialog = (root / "ui" / "finance_workspace" / "income_form_dialog.py").read_text(encoding="utf-8")
    source = (root / "services" / "income_service.py").read_text(encoding="utf-8")
    helper = source.split("def create_tuition_credit_only(", 1)[1].split(
        'def create_tuition_payment_with_credit(', 1
    )[0]
    assert "TuitionAdjustmentService(" in helper
    assert "service.credit_adjustment(" in helper
    assert "Income(" not in helper
    assert "create_income(" not in helper
    assert "idempotency_key=idempotency_key" in helper
    assert "cap_to_outstanding=True" in helper
    assert "return service.credit_adjustment(" in helper
    assert "if is_credit_only:" in dialog
    assert "self.accept()\n                        return" in dialog
    assert dialog.index("if is_credit_only:") < dialog.index(
        "created = self._income_service.create_tuition_payment_with_credit("
    )
    assert 'self._credit_only_command_key = f"tuition-credit-only:{uuid4()}"' in dialog


def test_credit_service_keeps_ledger_audit_permission_and_finance_event():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "services" / "tuition_adjustment_service.py").read_text(encoding="utf-8")
    method = source.split("def credit_adjustment(", 1)[1]
    assert "self._validate_amount(amount)" in method
    assert "self._ensure_date_mutable(session, effective_date)" in method
    assert "session.commit()" in method
    assert "record_for_active_write(" in method
    assert "mirror_after_successful_commit(session)" in method
    assert "self._publish(adjustment)" in method
    assert "Income(" not in method


def test_credit_only_cap_is_enforced_after_write_reservation():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    source = (root / "services" / "tuition_adjustment_service.py").read_text(encoding="utf-8")
    credit = source.split("def credit_adjustment(", 1)[1]
    assert "cap_to_outstanding: bool = False" in credit
    assert "if cap_to_outstanding:" in credit
    assert "calculate_effective_tuition_accrual(" in credit
    assert "sum_active_tuition_for_enrollment(" in credit
    assert "value > owed" in credit
    assert credit.index("adjustments.acquire_command_lock(") < credit.index("if cap_to_outstanding:")
    assert credit.index("if cap_to_outstanding:") < credit.index("session.commit()")
