from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.services.enrollment_service import EnrollmentService, EnrollmentValidationError
from centermanager.services.tuition_discount_policy import (
    TuitionDiscountPolicy,
    TuitionDiscountPolicyError,
)


class _ClassContract:
    has_course_contract = True
    planned_sessions = 10
    course_fee = Decimal("1000000")


def test_fixed_discount_resolves_to_canonical_snapshot_amount():
    result = TuitionDiscountPolicy.resolve(
        Decimal("1000000"),
        discount_type="FIXED",
        discount_value="125000",
        source="manual",
        reason="Sibling discount",
    )

    assert result.discount_type == "FIXED"
    assert result.discount_value == Decimal("125000.0000")
    assert result.discount_amount == Decimal("125000.0000")
    assert result.discount_source == "MANUAL"
    assert result.discount_reason == "Sibling discount"
    assert result.discount_policy_version == "enrollment_discount_v1"


def test_percentage_discount_is_resolved_after_enrollment_gross_fee_proration():
    snapshot = EnrollmentService._snapshot_tuition_contract(
        _ClassContract(),
        enrolled_from_session=6,
        enrolled_until_session=10,
        discount_type="PERCENT",
        discount_value=Decimal("10"),
        discount_source="MANUAL",
        discount_reason="Campaign approved",
    )

    assert snapshot["agreed_course_fee"] == Decimal("500000.0000")
    assert snapshot["unit_fee"] == Decimal("100000.0000")
    assert snapshot["discount_value"] == Decimal("10.0000")
    assert snapshot["discount_amount"] == Decimal("50000.0000")


def test_percentage_discount_recalculates_when_gross_fee_is_overridden():
    snapshot = EnrollmentService._snapshot_tuition_contract(
        _ClassContract(),
        enrolled_from_session=1,
        enrolled_until_session=10,
        discount_type="PERCENT",
        discount_value=Decimal("10"),
        discount_source="MANUAL",
        discount_reason="Approved",
    )

    overridden = EnrollmentService._apply_agreed_fee_override(snapshot, Decimal("800000"))

    assert overridden["agreed_course_fee"] == Decimal("800000.0000")
    assert overridden["unit_fee"] == Decimal("80000.0000")
    assert overridden["discount_amount"] == Decimal("80000.0000")
    assert overridden["discount_value"] == Decimal("10.0000")


def test_fixed_discount_stays_fixed_when_gross_fee_is_overridden():
    snapshot = EnrollmentService._snapshot_tuition_contract(
        _ClassContract(),
        enrolled_from_session=1,
        enrolled_until_session=10,
        discount_type="FIXED",
        discount_value=Decimal("100000"),
        discount_source="MANUAL",
        discount_reason="Approved",
    )

    overridden = EnrollmentService._apply_agreed_fee_override(snapshot, Decimal("800000"))
    assert overridden["discount_amount"] == Decimal("100000.0000")


def test_discount_policy_rejects_invalid_values_and_over_discount():
    with pytest.raises(TuitionDiscountPolicyError, match="cannot exceed 100"):
        TuitionDiscountPolicy.resolve(
            1000, discount_type="PERCENT", discount_value=101
        )
    with pytest.raises(TuitionDiscountPolicyError, match="cannot exceed the agreed course fee"):
        TuitionDiscountPolicy.resolve(
            1000, discount_type="FIXED", discount_value=1001
        )
    with pytest.raises(TuitionDiscountPolicyError, match="cannot be negative"):
        TuitionDiscountPolicy.resolve(
            1000, discount_type="FIXED", discount_value=-1
        )


def test_legacy_discount_amount_remains_backward_compatible_snapshot():
    snapshot = EnrollmentService._snapshot_tuition_contract(
        _ClassContract(),
        enrolled_from_session=1,
        enrolled_until_session=10,
        discount_amount=Decimal("75000"),
    )

    assert snapshot["discount_amount"] == Decimal("75000.0000")
    assert snapshot["discount_type"] == "FIXED"
    assert snapshot["discount_value"] == Decimal("75000.0000")
    assert snapshot["discount_policy_version"] == "legacy_fixed_v1"


def test_rule_and_legacy_amount_cannot_be_mixed():
    with pytest.raises(EnrollmentValidationError, match="either discount_amount"):
        EnrollmentService._snapshot_tuition_contract(
            _ClassContract(),
            enrolled_from_session=1,
            enrolled_until_session=10,
            discount_amount=100,
            discount_type="FIXED",
            discount_value=100,
        )


def test_accrual_boundary_consumes_only_enrollment_discount_snapshot():
    root = Path(__file__).resolve().parents[1]
    accrual_source = (
        root / "src/centermanager/services/tuition_accrual_service.py"
    ).read_text(encoding="utf-8")

    assert "Decimal(enrollment.discount_amount or 0)" in accrual_source
    assert "tuition_discount_policy" not in accrual_source
    assert "discount_type" not in accrual_source
    assert "discount_value" not in accrual_source


def test_manual_discount_contract_requires_source_and_reason_in_enroll_path():
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "src/centermanager/services/enrollment_service.py"
    ).read_text(encoding="utf-8")

    assert "Discount source is required for a discount rule." in source
    assert "A reason is required for a manual discount." in source
    assert 'action="TUITION_ENROLLMENT_DISCOUNT"' in source
    assert "Capability.TUITION_ENROLLMENT_OVERRIDE" in source


def test_migration_extends_snapshot_without_rewriting_historical_discount_amount():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "migrations/versions/1e10a036_enrollment_discount_snapshot.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "1e10a035"' in migration
    assert '"discount_type"' in migration
    assert '"discount_value"' in migration
    assert '"discount_source"' in migration
    assert '"discount_reason"' in migration
    assert '"discount_policy_version"' in migration
    assert "UPDATE enrollments" not in migration
