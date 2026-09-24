from decimal import Decimal
from types import SimpleNamespace

import pytest

from centermanager.models.enrollment import Enrollment
from centermanager.services.enrollment_service import (
    EnrollmentService,
    EnrollmentValidationError,
)


def _class_contract(*, fee=3_600_000, planned_sessions=24, complete=True):
    return SimpleNamespace(
        has_course_contract=complete,
        course_fee=fee,
        planned_sessions=planned_sessions,
    )


def _snapshot(class_obj, *, start=1, until=None, discount=0):
    return EnrollmentService._snapshot_tuition_contract(
        class_obj,
        enrolled_from_session=start,
        enrolled_until_session=until,
        discount_amount=discount,
    )


def test_full_course_snapshot_preserves_unit_fee_invariant():
    snapshot = _snapshot(_class_contract())

    assert snapshot["agreed_course_fee"] == Decimal("3600000.0000")
    assert snapshot["planned_sessions"] == 24
    assert snapshot["unit_fee"] == Decimal("150000.0000")
    assert snapshot["enrolled_from_session"] == 1
    assert snapshot["enrolled_until_session"] == 24
    assert snapshot["unit_fee"] == (
        snapshot["agreed_course_fee"] / snapshot["planned_sessions"]
    )


def test_mid_course_snapshot_uses_effective_enrollment_session_count():
    snapshot = _snapshot(_class_contract(), start=9)

    assert snapshot["enrolled_from_session"] == 9
    assert snapshot["enrolled_until_session"] == 24
    assert snapshot["planned_sessions"] == 16
    assert snapshot["agreed_course_fee"] == Decimal("2400000.0000")
    assert snapshot["unit_fee"] == Decimal("150000.0000")
    assert snapshot["unit_fee"] == (
        snapshot["agreed_course_fee"] / snapshot["planned_sessions"]
    )


def test_explicit_mid_course_range_is_auditable():
    snapshot = _snapshot(_class_contract(), start=9, until=12, discount=100_000)

    assert snapshot["planned_sessions"] == 4
    assert snapshot["agreed_course_fee"] == Decimal("600000.0000")
    assert snapshot["unit_fee"] == Decimal("150000.0000")
    assert snapshot["discount_amount"] == Decimal("100000.0000")


def test_snapshot_rejects_incomplete_class_contract():
    with pytest.raises(EnrollmentValidationError, match="incomplete"):
        _snapshot(_class_contract(complete=False))


@pytest.mark.parametrize(
    ("start", "until"),
    [
        (0, None),
        (25, None),
        (9, 8),
        (9, 25),
    ],
)
def test_snapshot_rejects_invalid_effective_session_range(start, until):
    with pytest.raises(EnrollmentValidationError):
        _snapshot(_class_contract(), start=start, until=until)


def test_snapshot_rejects_invalid_discount():
    with pytest.raises(EnrollmentValidationError, match="cannot be negative"):
        _snapshot(_class_contract(), discount=-1)

    with pytest.raises(EnrollmentValidationError, match="cannot exceed"):
        _snapshot(_class_contract(), discount=3_600_001)


def test_legacy_enrollment_explicitly_reports_unresolved_contract():
    enrollment = Enrollment(
        student_id=1,
        class_id=1,
        class_name="Legacy Class",
        status="ACTIVE",
    )

    assert enrollment.has_tuition_contract is False
    assert enrollment.contracted_session_count is None


def test_enrollment_contract_helpers_report_effective_range():
    enrollment = Enrollment(
        student_id=1,
        class_id=1,
        agreed_course_fee=Decimal("2400000.0000"),
        planned_sessions=16,
        unit_fee=Decimal("150000.0000"),
        enrolled_from_session=9,
        enrolled_until_session=24,
        discount_amount=Decimal("0"),
        status="ACTIVE",
    )

    assert enrollment.has_tuition_contract is True
    assert enrollment.contracted_session_count == 16
