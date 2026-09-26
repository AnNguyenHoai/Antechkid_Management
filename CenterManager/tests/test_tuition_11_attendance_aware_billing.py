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
    LEGACY_SESSION_ONLY_POLICY,
    BillableSessionPolicy,
)


def _enrollment(policy=ATTENDANCE_AWARE_POLICY_V1):
    enrollment = SimpleNamespace(
        id=71,
        student_id=9,
        class_id=4,
        agreed_course_fee=Decimal("400000"),
        planned_sessions=4,
        unit_fee=Decimal("100000"),
        enrolled_from_session=1,
        enrolled_until_session=4,
        discount_amount=Decimal("0"),
        billing_policy_version=policy,
    )
    enrollment.has_tuition_contract = True
    return enrollment


def _attendance(session_id, status):
    if status is None:
        return None
    return SimpleNamespace(session_id=session_id, student_id=9, status=status)


def _session(number, session_status, attendance_status=None):
    attendance = _attendance(number, attendance_status)
    return SimpleNamespace(
        id=number,
        class_id=4,
        session_number=number,
        title=f"Lesson {number}",
        status=session_status,
        scheduled_date=date(2026, 9, number),
        actual_date=(date(2026, 9, number) if session_status == SessionStatus.COMPLETED.value else None),
        attendances=([attendance] if attendance is not None else []),
    )


@pytest.mark.parametrize(
    ("attendance_status", "expected", "reason"),
    [
        (AttendanceStatus.PRESENT.value, True, BillableSessionPolicy.REASON_ATTENDANCE_PRESENT),
        (AttendanceStatus.LATE.value, True, BillableSessionPolicy.REASON_ATTENDANCE_LATE),
        (AttendanceStatus.ABSENT.value, True, BillableSessionPolicy.REASON_ATTENDANCE_ABSENT),
        (AttendanceStatus.EXCUSED.value, False, BillableSessionPolicy.REASON_ATTENDANCE_EXCUSED),
        (None, True, BillableSessionPolicy.REASON_ATTENDANCE_MISSING),
    ],
)
def test_completed_session_applies_attendance_v1(attendance_status, expected, reason):
    session = _session(2, SessionStatus.COMPLETED.value, attendance_status)
    attendance = session.attendances[0] if session.attendances else None

    decision = BillableSessionPolicy.evaluate(session, _enrollment(), attendance)

    assert decision.billable is expected
    assert decision.reason == reason
    assert decision.attendance_status == attendance_status
    assert decision.policy_version == ATTENDANCE_AWARE_POLICY_V1


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
def test_non_completed_session_never_becomes_billable_from_attendance(
    session_status, attendance_status
):
    session = _session(2, session_status, attendance_status)
    attendance = session.attendances[0] if session.attendances else None

    decision = BillableSessionPolicy.evaluate(session, _enrollment(), attendance)

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_NOT_COMPLETED


def test_legacy_policy_preserves_pre_tuition_11_meaning_even_when_excused():
    session = _session(2, SessionStatus.COMPLETED.value, AttendanceStatus.EXCUSED.value)

    decision = BillableSessionPolicy.evaluate(
        session,
        _enrollment(LEGACY_SESSION_ONLY_POLICY),
        session.attendances[0],
    )

    assert decision.billable is True
    assert decision.reason == BillableSessionPolicy.REASON_BILLABLE
    assert decision.policy_version == LEGACY_SESSION_ONLY_POLICY


def test_unknown_policy_fails_closed_instead_of_reinterpreting_history():
    session = _session(2, SessionStatus.COMPLETED.value, AttendanceStatus.PRESENT.value)

    decision = BillableSessionPolicy.evaluate(
        session,
        _enrollment("future_policy_v99"),
        session.attendances[0],
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_UNSUPPORTED_POLICY


def test_accrual_uses_attendance_attached_to_sessions_for_composed_read_models():
    sessions = [
        _session(1, SessionStatus.COMPLETED.value, AttendanceStatus.PRESENT.value),
        _session(2, SessionStatus.COMPLETED.value, AttendanceStatus.EXCUSED.value),
        _session(3, SessionStatus.COMPLETED.value, AttendanceStatus.ABSENT.value),
        _session(4, SessionStatus.COMPLETED.value, None),
    ]

    result = TuitionAccrualService.calculate_from_records(
        _enrollment(), sessions, date(2026, 9, 30)
    )

    assert result.billing_policy_version == ATTENDANCE_AWARE_POLICY_V1
    assert result.billable_session_numbers == (1, 3, 4)
    assert result.billable_sessions == 3
    assert result.gross_accrued == Decimal("300000.0000")
    assert result.net_accrued == Decimal("300000.0000")


def test_explicit_attendance_map_is_supported_for_repository_backed_accrual():
    sessions = [
        _session(1, SessionStatus.COMPLETED.value),
        _session(2, SessionStatus.COMPLETED.value),
    ]
    attendance_map = {
        1: _attendance(1, AttendanceStatus.EXCUSED.value),
        2: _attendance(2, AttendanceStatus.LATE.value),
    }

    result = TuitionAccrualService.calculate_from_records(
        _enrollment(),
        sessions,
        date(2026, 9, 30),
        attendance_by_session_id=attendance_map,
    )

    assert result.billable_session_numbers == (2,)


def test_tuition_11_migration_keeps_preexisting_rows_on_legacy_policy():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "migrations/versions/1e10a033_enrollment_billing_policy_version.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "1e10a033"' in migration
    assert 'down_revision = "1e10a032"' in migration
    assert "legacy_session_only_v1" in migration
    assert "UPDATE enrollments SET billing_policy_version" in migration
