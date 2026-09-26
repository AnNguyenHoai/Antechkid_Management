from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.attendance import AttendanceStatus
from centermanager.models.session import SessionStatus
from centermanager.services.tuition_accrual_service import TuitionAccrualService
from centermanager.services.tuition_policy import (
    ATTENDANCE_AWARE_POLICY_V1,
    ATTENDANCE_AWARE_POLICY_V2,
    CURRENT_BILLING_POLICY_VERSION,
    SUPPORTED_BILLING_POLICY_VERSIONS,
    BillableSessionPolicy,
)


def _enrollment(policy=ATTENDANCE_AWARE_POLICY_V2):
    enrollment = SimpleNamespace(
        id=118,
        student_id=19,
        class_id=7,
        agreed_course_fee=Decimal("400000"),
        planned_sessions=4,
        unit_fee=Decimal("100000"),
        enrolled_from_session=1,
        enrolled_until_session=4,
        discount_amount=Decimal("0"),
        billing_policy_version=policy,
        freezes=[],
    )
    enrollment.has_tuition_contract = True
    return enrollment


def _attendance(session_id, status):
    if status is None:
        return None
    return SimpleNamespace(session_id=session_id, student_id=19, status=status)


def _session(number, session_status, attendance_status=None):
    attendance = _attendance(number, attendance_status)
    return SimpleNamespace(
        id=number,
        class_id=7,
        session_number=number,
        title=f"Lesson {number}",
        status=session_status,
        scheduled_date=date(2026, 9, number),
        actual_date=(
            date(2026, 9, number)
            if session_status == SessionStatus.COMPLETED.value
            else None
        ),
        attendances=([attendance] if attendance is not None else []),
    )


@pytest.mark.parametrize(
    ("attendance_status", "reason"),
    [
        (AttendanceStatus.PRESENT.value, BillableSessionPolicy.REASON_ATTENDANCE_PRESENT),
        (AttendanceStatus.LATE.value, BillableSessionPolicy.REASON_ATTENDANCE_LATE),
        (AttendanceStatus.ABSENT.value, BillableSessionPolicy.REASON_ATTENDANCE_ABSENT),
        (None, BillableSessionPolicy.REASON_ATTENDANCE_MISSING),
    ],
)
def test_attendance_v2_bills_billable_known_attendance_states_for_completed_session(
    attendance_status, reason
):
    teaching_session = _session(
        2,
        SessionStatus.COMPLETED.value,
        attendance_status,
    )
    attendance = (
        teaching_session.attendances[0]
        if teaching_session.attendances
        else None
    )

    decision = BillableSessionPolicy.evaluate(
        teaching_session,
        _enrollment(),
        attendance,
    )

    assert decision.billable is True
    assert decision.reason == reason
    assert decision.attendance_status == attendance_status
    assert decision.policy_version == ATTENDANCE_AWARE_POLICY_V2


def test_attendance_v2_excused_is_not_billable():
    teaching_session = _session(
        2,
        SessionStatus.COMPLETED.value,
        AttendanceStatus.EXCUSED.value,
    )

    decision = BillableSessionPolicy.evaluate(
        teaching_session,
        _enrollment(),
        teaching_session.attendances[0],
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_ATTENDANCE_EXCUSED
    assert decision.attendance_status == AttendanceStatus.EXCUSED.value
    assert decision.policy_version == ATTENDANCE_AWARE_POLICY_V2


@pytest.mark.parametrize(
    "session_status",
    [
        SessionStatus.SCHEDULED.value,
        SessionStatus.POSTPONED.value,
        SessionStatus.CANCELLED.value,
    ],
)
@pytest.mark.parametrize(
    "attendance_status",
    [
        AttendanceStatus.PRESENT.value,
        AttendanceStatus.LATE.value,
        AttendanceStatus.ABSENT.value,
        AttendanceStatus.EXCUSED.value,
        None,
    ],
)
def test_attendance_v2_cannot_override_session_lifecycle_gate(
    session_status,
    attendance_status,
):
    teaching_session = _session(2, session_status, attendance_status)
    attendance = (
        teaching_session.attendances[0]
        if teaching_session.attendances
        else None
    )

    decision = BillableSessionPolicy.evaluate(
        teaching_session,
        _enrollment(),
        attendance,
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_NOT_COMPLETED


def test_attendance_v1_excused_semantics_are_not_reinterpreted():
    teaching_session = _session(
        2,
        SessionStatus.COMPLETED.value,
        AttendanceStatus.EXCUSED.value,
    )

    decision = BillableSessionPolicy.evaluate(
        teaching_session,
        _enrollment(ATTENDANCE_AWARE_POLICY_V1),
        teaching_session.attendances[0],
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_ATTENDANCE_EXCUSED
    assert decision.policy_version == ATTENDANCE_AWARE_POLICY_V1


def test_attendance_v2_unknown_attendance_still_fails_closed():
    teaching_session = _session(2, SessionStatus.COMPLETED.value)

    decision = BillableSessionPolicy.evaluate(
        teaching_session,
        _enrollment(),
        "FUTURE_STATUS",
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_ATTENDANCE_UNKNOWN


def test_attendance_v2_accrual_excludes_excused_but_includes_absent_sessions():
    sessions = [
        _session(1, SessionStatus.COMPLETED.value, AttendanceStatus.PRESENT.value),
        _session(2, SessionStatus.COMPLETED.value, AttendanceStatus.EXCUSED.value),
        _session(3, SessionStatus.COMPLETED.value, AttendanceStatus.ABSENT.value),
        _session(4, SessionStatus.COMPLETED.value, None),
    ]

    result = TuitionAccrualService.calculate_from_records(
        _enrollment(),
        sessions,
        date(2026, 9, 30),
    )

    assert result.billing_policy_version == ATTENDANCE_AWARE_POLICY_V2
    assert result.billable_session_numbers == (1, 3, 4)
    assert result.billable_sessions == 3
    assert result.gross_accrued == Decimal("300000.0000")
    assert result.net_accrued == Decimal("300000.0000")


def test_attendance_v2_is_current_and_new_enrollment_model_default():
    root = Path(__file__).resolve().parents[1]
    model = (root / "src/centermanager/models/enrollment.py").read_text(
        encoding="utf-8"
    )

    assert CURRENT_BILLING_POLICY_VERSION == ATTENDANCE_AWARE_POLICY_V2
    assert ATTENDANCE_AWARE_POLICY_V1 in SUPPORTED_BILLING_POLICY_VERSIONS
    assert ATTENDANCE_AWARE_POLICY_V2 in SUPPORTED_BILLING_POLICY_VERSIONS
    assert 'default="attendance_v2"' in model
