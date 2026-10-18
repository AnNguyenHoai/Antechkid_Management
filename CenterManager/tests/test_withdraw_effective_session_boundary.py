# -*- coding: utf-8 -*-
"""Regression coverage for exact Enrollment withdrawal session boundaries."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from centermanager.models.session import SessionStatus
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.enrollment_service import EnrollmentService, EnrollmentStatus
from centermanager.services.tuition_policy import BillableSessionPolicy


def _session(number: int, status: str = SessionStatus.SCHEDULED.value):
    return SimpleNamespace(
        id=number,
        class_id=10,
        session_number=number,
        status=status,
        scheduled_date=date(2026, 10, number if number <= 28 else 28),
        actual_date=None,
    )


def _enrollment(**overrides):
    data = dict(
        id=1,
        student_id=2,
        class_id=10,
        status=EnrollmentStatus.WITHDRAWN.value,
        enrolled_from_session=1,
        enrolled_until_session=12,
        withdrawn_from_session=10,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 9),
        billing_policy_version="attendance_v2",
        freezes=[],
    )
    data.update(overrides)
    return SimpleNamespace(**data)


def test_default_withdraw_boundary_is_first_session_after_latest_completed():
    enrollment = _enrollment(status=EnrollmentStatus.ACTIVE.value, withdrawn_from_session=None)
    sessions = [
        _session(8, SessionStatus.COMPLETED.value),
        _session(9, SessionStatus.COMPLETED.value),
        _session(10, SessionStatus.SCHEDULED.value),
        _session(11, SessionStatus.SCHEDULED.value),
    ]

    boundary = EnrollmentService._resolve_withdrawn_from_session(
        enrollment,
        sessions,
    )

    assert boundary == 10


def test_withdraw_before_any_completed_session_starts_at_enrollment_first_session():
    enrollment = _enrollment(
        status=EnrollmentStatus.ACTIVE.value,
        withdrawn_from_session=None,
        enrolled_from_session=3,
        enrolled_until_session=12,
    )

    assert EnrollmentService._resolve_withdrawn_from_session(
        enrollment,
        [_session(3), _session(4)],
    ) == 3


def test_attendance_roster_excludes_withdrawal_boundary_and_later_sessions():
    enrollment = _enrollment()

    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(9),
    ) is True
    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(10),
    ) is False
    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(11),
    ) is False


def test_tuition_policy_stops_at_withdrawal_boundary():
    enrollment = _enrollment()

    before = _session(9, SessionStatus.COMPLETED.value)
    after = _session(10, SessionStatus.COMPLETED.value)

    assert BillableSessionPolicy._session_gate(before, enrollment) is None
    decision = BillableSessionPolicy._session_gate(after, enrollment)
    assert decision is not None
    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_AFTER_WITHDRAWAL_BOUNDARY


def test_historical_overlap_range_ends_before_withdrawal_boundary():
    enrollment = _enrollment()

    assert EnrollmentService._effective_historical_range(
        enrollment,
        [_session(number) for number in range(1, 13)],
    ) == (1, 9)


def test_migration_and_restore_contract_preserve_exact_boundary():
    root = Path(__file__).resolve().parent.parent
    migration = (
        root
        / "migrations"
        / "versions"
        / "1e10a042_enrollment_withdrawal_session_boundary.py"
    ).read_text(encoding="utf-8")
    service = (
        root / "src" / "centermanager" / "services" / "enrollment_service.py"
    ).read_text(encoding="utf-8")
    verifier = (
        root / "src" / "centermanager" / "database" / "migration.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "1e10a041"' in migration
    assert '"withdrawn_from_session"' in migration
    assert "enrollment.withdrawn_from_session = None" in service
    assert '"withdrawn_from_session"' in verifier
