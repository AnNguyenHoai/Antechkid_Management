from types import SimpleNamespace

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.tuition_policy import BillableSessionPolicy


def _enrollment(*, class_id=10, start=3, end=8, attendance_status=None):
    return SimpleNamespace(
        class_id=class_id,
        enrolled_from_session=start,
        enrolled_until_session=end,
        attendance_status=attendance_status,
    )


def _session(number, status, *, class_id=10, attendance_status=None):
    return SimpleNamespace(
        class_id=class_id,
        session_number=number,
        status=status,
        attendance_status=attendance_status,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (SessionStatus.COMPLETED.value, True),
        (SessionStatus.SCHEDULED.value, False),
        (SessionStatus.POSTPONED.value, False),
        (SessionStatus.CANCELLED.value, False),
    ],
)
def test_phase_1_status_policy(status, expected):
    session = _session(5, status)

    assert BillableSessionPolicy.is_billable(session, _enrollment()) is expected


def test_effective_range_is_inclusive_at_both_boundaries():
    enrollment = _enrollment(start=3, end=8)

    assert BillableSessionPolicy.is_billable(
        _session(3, SessionStatus.COMPLETED.value), enrollment
    )
    assert BillableSessionPolicy.is_billable(
        _session(8, SessionStatus.COMPLETED.value), enrollment
    )


def test_completed_session_before_effective_range_is_not_billable():
    decision = BillableSessionPolicy.evaluate(
        _session(2, SessionStatus.COMPLETED.value),
        _enrollment(start=3, end=8),
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_OUTSIDE_RANGE


def test_completed_session_after_effective_range_is_not_billable():
    decision = BillableSessionPolicy.evaluate(
        _session(9, SessionStatus.COMPLETED.value),
        _enrollment(start=3, end=8),
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_OUTSIDE_RANGE


def test_session_must_belong_to_same_class_when_identity_is_available():
    decision = BillableSessionPolicy.evaluate(
        _session(5, SessionStatus.COMPLETED.value, class_id=20),
        _enrollment(class_id=10),
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_CLASS_MISMATCH


def test_legacy_unresolved_enrollment_is_not_silently_billed():
    decision = BillableSessionPolicy.evaluate(
        _session(5, SessionStatus.COMPLETED.value),
        _enrollment(start=None, end=None),
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_UNRESOLVED_RANGE


def test_invalid_session_number_is_not_billable():
    decision = BillableSessionPolicy.evaluate(
        _session(0, SessionStatus.COMPLETED.value),
        _enrollment(start=1, end=8),
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_INVALID_SESSION_NUMBER


def test_status_change_recomputes_billability_deterministically():
    enrollment = _enrollment(start=1, end=8)
    session = _session(4, SessionStatus.SCHEDULED.value)

    assert BillableSessionPolicy.is_billable(session, enrollment) is False

    session.status = SessionStatus.COMPLETED.value
    assert BillableSessionPolicy.is_billable(session, enrollment) is True

    session.status = SessionStatus.CANCELLED.value
    assert BillableSessionPolicy.is_billable(session, enrollment) is False


def test_filter_billable_preserves_order_and_applies_both_status_and_range():
    enrollment = _enrollment(start=3, end=6)
    sessions = [
        _session(2, SessionStatus.COMPLETED.value),
        _session(3, SessionStatus.COMPLETED.value),
        _session(4, SessionStatus.POSTPONED.value),
        _session(5, SessionStatus.COMPLETED.value),
        _session(6, SessionStatus.COMPLETED.value),
        _session(7, SessionStatus.COMPLETED.value),
    ]

    result = BillableSessionPolicy.filter_billable(sessions, enrollment)

    assert [item.session_number for item in result] == [3, 5, 6]


def test_attendance_is_intentionally_ignored_in_phase_1():
    enrollment = _enrollment(start=1, end=8, attendance_status="Absent")
    completed = _session(
        5,
        SessionStatus.COMPLETED.value,
        attendance_status="Absent",
    )

    assert BillableSessionPolicy.is_billable(completed, enrollment) is True


def test_policy_has_no_finance_period_dependency():
    source = __import__(
        "centermanager.services.tuition_policy",
        fromlist=["BillableSessionPolicy"],
    )
    path = source.__file__
    with open(path, encoding="utf-8") as handle:
        content = handle.read()

    assert "FinancePeriod" not in content
    assert "AccountingPeriod" not in content
