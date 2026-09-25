from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from centermanager.models.attendance import AttendanceStatus
from centermanager.models.enrollment_freeze import EnrollmentFreeze
from centermanager.models.session import SessionStatus
from centermanager.services.enrollment_service import (
    EnrollmentService,
    EnrollmentValidationError,
)
from centermanager.services.tuition_accrual_service import TuitionAccrualService
from centermanager.services.tuition_policy import ATTENDANCE_AWARE_POLICY_V1, BillableSessionPolicy


def _freeze(start, end=None, reason="Family pause"):
    return SimpleNamespace(start_session=start, end_session=end, reason=reason, is_open=end is None)


def _enrollment(freezes=None):
    enrollment = SimpleNamespace(
        id=81,
        student_id=9,
        class_id=4,
        status="ACTIVE",
        class_name="Python 1",
        agreed_course_fee=Decimal("600000"),
        planned_sessions=6,
        unit_fee=Decimal("100000"),
        enrolled_from_session=1,
        enrolled_until_session=6,
        discount_amount=Decimal("0"),
        billing_policy_version=ATTENDANCE_AWARE_POLICY_V1,
        freezes=list(freezes or []),
    )
    enrollment.has_tuition_contract = True
    return enrollment


def _session(number, attendance_status=AttendanceStatus.PRESENT.value):
    attendance = SimpleNamespace(session_id=number, student_id=9, status=attendance_status)
    return SimpleNamespace(
        id=number,
        class_id=4,
        session_number=number,
        status=SessionStatus.COMPLETED.value,
        scheduled_date=date(2026, 9, number),
        actual_date=date(2026, 9, number),
        attendances=[attendance],
    )


def test_freeze_range_is_non_billable_without_changing_session_status():
    enrollment = _enrollment([_freeze(3, 4)])
    sessions = [_session(number) for number in range(1, 7)]

    result = TuitionAccrualService.calculate_from_records(
        enrollment, sessions, date(2026, 9, 30)
    )

    assert result.billable_session_numbers == (1, 2, 5, 6)
    assert result.net_accrued == Decimal("400000.0000")
    assert all(item.status == SessionStatus.COMPLETED.value for item in sessions)


def test_open_freeze_pauses_from_start_until_it_is_closed():
    enrollment = _enrollment([_freeze(3)])

    assert BillableSessionPolicy.evaluate(_session(2), enrollment).billable is True
    decision = BillableSessionPolicy.evaluate(_session(3), enrollment)
    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_ENROLLMENT_FROZEN
    assert BillableSessionPolicy.evaluate(_session(6), enrollment).billable is False


def test_resume_range_reactivates_accrual_after_last_frozen_session():
    enrollment = _enrollment([_freeze(3, 4)])

    assert BillableSessionPolicy.evaluate(_session(4), enrollment).billable is False
    assert BillableSessionPolicy.evaluate(_session(5), enrollment).billable is True


def test_freeze_gate_precedes_attendance_policy():
    enrollment = _enrollment([_freeze(2, 2)])
    session = _session(2, AttendanceStatus.PRESENT.value)

    decision = BillableSessionPolicy.evaluate(session, enrollment, session.attendances[0])

    assert decision.billable is False
    assert decision.reason == BillableSessionPolicy.REASON_ENROLLMENT_FROZEN


def test_range_overlap_handles_closed_and_open_ranges():
    assert EnrollmentService._ranges_overlap(3, 5, 5, 7) is True
    assert EnrollmentService._ranges_overlap(3, 5, 6, 7) is False
    assert EnrollmentService._ranges_overlap(3, None, 99, 100) is True
    assert EnrollmentService._ranges_overlap(3, 5, 6, None) is False


def test_freeze_and_resume_reason_are_required_before_storage_access():
    service = EnrollmentService(MagicMock(), repository_provider=MagicMock(), audit_service=MagicMock())

    with pytest.raises(EnrollmentValidationError, match="Freeze reason is required"):
        service.freeze(81, 3, "  ")
    with pytest.raises(EnrollmentValidationError, match="Resume reason is required"):
        service.resume(81, 4, "")


def test_migration_is_new_head_and_does_not_infer_historical_freezes():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations/versions/1e10a034_enrollment_tuition_freeze.py").read_text(encoding="utf-8")

    assert 'revision = "1e10a034"' in migration
    assert 'down_revision = "1e10a033"' in migration
    assert 'op.create_table(\n        "enrollment_freezes"' in migration
    assert "start_session >= 1" in migration
    assert "end_session IS NULL OR end_session >= start_session" in migration
    assert "INSERT INTO enrollment_freezes" not in migration
    assert "FinancePeriod" not in migration


def test_service_audits_freeze_resume_and_blocks_terminal_transition_while_open():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/services/enrollment_service.py").read_text(encoding="utf-8")

    assert 'action="TUITION_ENROLLMENT_FREEZE"' in source
    assert 'action="TUITION_ENROLLMENT_RESUME"' in source
    assert "record_in_session(" in source
    assert "Resume the open tuition freeze before completing or withdrawing" in source
    assert "Freeze cannot start on or before an already completed session" in source
    assert "Capability.STUDENT_UPDATE" in source
    assert "FinancePeriod" not in source


def test_ui_projects_freeze_resume_with_write_and_domain_state_guards():
    root = Path(__file__).resolve().parents[1]
    source = (root / "src/centermanager/ui/student_workspace/enrollment_widget.py").read_text(encoding="utf-8")

    assert 'Button("Pause tuition"' in source
    assert 'Button("Resume tuition"' in source
    assert "self._write_enabled and open_freeze is None" in source
    assert "self._write_enabled and open_freeze is not None" in source
    assert "self._enrollment_service.freeze(" in source
    assert "self._enrollment_service.resume(" in source
    assert "date.today" not in source


def test_freeze_model_preserves_auditable_reason_and_resume_metadata():
    freeze = EnrollmentFreeze(
        enrollment_id=81,
        start_session=3,
        reason="Travel",
        created_by="manager",
    )
    assert freeze.is_open is True
    assert freeze.contains_session(3) is True
    assert freeze.contains_session(99) is True
    freeze.end_session = 4
    freeze.resume_reason = "Returned"
    freeze.resumed_by = "manager"
    assert freeze.is_open is False
    assert freeze.contains_session(4) is True
    assert freeze.contains_session(5) is False
