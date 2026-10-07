# -*- coding: utf-8 -*-
"""PR I — Enrollment restore/re-enrollment regression coverage."""
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.enrollment_service import (
    EnrollmentRangeOverlapError,
    EnrollmentService,
)
from centermanager.services.tuition_policy import BillableSessionPolicy


ROOT = Path("src/centermanager")


def _session(number: int, on_date: date, *, class_id: int = 20):
    return SimpleNamespace(
        id=number,
        class_id=class_id,
        session_number=number,
        scheduled_date=on_date,
        actual_date=on_date,
        status=SessionStatus.COMPLETED.value,
    )


def _enrollment(
    enrollment_id: int,
    *,
    status: str = "WITHDRAWN",
    start: int = 1,
    end: int = 10,
    ended_on: date | None = date(2026, 1, 15),
):
    return SimpleNamespace(
        id=enrollment_id,
        student_id=10,
        class_id=20,
        status=status,
        enrolled_from_session=start,
        enrolled_until_session=end,
        end_date=ended_on,
    )


def test_withdrawn_contract_effective_range_stops_at_withdrawal_date():
    enrollment = _enrollment(101, start=1, end=10, ended_on=date(2026, 1, 15))
    sessions = [
        _session(1, date(2026, 1, 5)),
        _session(2, date(2026, 1, 12)),
        _session(3, date(2026, 1, 19)),
    ]

    assert EnrollmentService._effective_historical_range(enrollment, sessions) == (1, 2)


def test_reenrollment_guard_rejects_overlap_with_historical_contract():
    enrollment = _enrollment(101, start=1, end=10, ended_on=date(2026, 1, 15))
    sessions = [
        _session(1, date(2026, 1, 5)),
        _session(2, date(2026, 1, 12)),
        _session(3, date(2026, 1, 19)),
    ]

    with pytest.raises(EnrollmentRangeOverlapError, match="Enrollment #101"):
        EnrollmentService._ensure_no_overlapping_contract(
            [enrollment],
            sessions,
            new_start=2,
            new_end=5,
        )


def test_reenrollment_guard_allows_non_overlapping_new_contract():
    enrollment = _enrollment(101, start=1, end=10, ended_on=date(2026, 1, 15))
    sessions = [
        _session(1, date(2026, 1, 5)),
        _session(2, date(2026, 1, 12)),
        _session(3, date(2026, 1, 19)),
    ]

    EnrollmentService._ensure_no_overlapping_contract(
        [enrollment],
        sessions,
        new_start=3,
        new_end=10,
    )


def test_tuition_does_not_accrue_after_withdrawal_end_date():
    enrollment = SimpleNamespace(
        class_id=20,
        enrolled_from_session=1,
        enrolled_until_session=10,
        end_date=date(2026, 1, 15),
        freezes=[],
        billing_policy_version="legacy_session_only_v1",
    )
    decision = BillableSessionPolicy.evaluate(
        _session(3, date(2026, 1, 19)),
        enrollment,
    )

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_AFTER_ENROLLMENT_END


def test_attendance_roster_does_not_extend_past_withdrawal_date():
    enrollment = SimpleNamespace(
        enrolled_from_session=1,
        enrolled_until_session=10,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 15),
    )

    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(2, date(2026, 1, 12)),
    ) is True
    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(3, date(2026, 1, 19)),
    ) is False


def test_restore_reuses_same_enrollment_identity_and_is_audited():
    source = (ROOT / "services/enrollment_service.py").read_text(encoding="utf-8")
    restore = source[source.index("    def restore("):source.index("    def _transition(", source.index("    def restore("))]

    assert "enrollment.status = EnrollmentStatus.ACTIVE.value" in restore
    assert "enrollment.end_date = None" in restore
    assert 'action="ENROLLMENT_RESTORED"' in restore
    assert 'self._publish_change(enrollment, "RESTORED", previous_status)' in restore
    assert "repo.add(" not in restore


def test_withdraw_is_explicit_and_audited():
    source = (ROOT / "services/enrollment_service.py").read_text(encoding="utf-8")
    assert '"ENROLLMENT_WITHDRAWN"' in source
    assert '"reason": transition_reason' in source


def test_class_enrollment_ui_distinguishes_restore_reenroll_and_withdraw():
    source = (ROOT / "ui/class_workspace/class_enrollment_dialog.py").read_text(encoding="utf-8")

    assert '"← Withdraw"' in source
    assert '"Restore existing"' in source
    assert '"Create new Enrollment"' in source
    assert "get_latest_restorable_enrollment" in source
    assert "restore_student(" in source
    assert "A withdrawal reason is required." in source
    assert "A restore reason is required." in source


def test_class_service_validates_restore_identity_before_mutation():
    source = (ROOT / "services/class_service.py").read_text(encoding="utf-8")
    section = source[source.index("    def restore_student("):source.index("    def enroll_student(", source.index("    def restore_student("))]

    assert section.index("candidate =") < section.index(").restore(enrollment_id, reason=reason)")
    assert "candidate.student_id != student_id" in section
    assert "candidate.class_id != class_id" in section


def test_outstanding_remains_enrollment_centric_not_hidden_by_student_class_grouping():
    source = (ROOT / "services/outstanding_service.py").read_text(encoding="utf-8")
    assert "seen_enrollment_ids = set()" in source
    assert "GROUP BY student_id" not in source
