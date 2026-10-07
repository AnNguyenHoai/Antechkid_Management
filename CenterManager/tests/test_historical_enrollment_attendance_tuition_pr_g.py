from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from centermanager.models.attendance import AttendanceStatus
from centermanager.models.session import SessionStatus
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.tuition_accrual_service import TuitionAccrualService


ROOT = Path("src/centermanager")


def _session(number: int):
    return SimpleNamespace(
        id=number,
        class_id=10,
        session_number=number,
        scheduled_date=date(2026, 10, number),
        actual_date=date(2026, 10, number),
        status=SessionStatus.COMPLETED.value,
        attendances=[],
    )


def _enrollment(start_session: int, student_id: int = 7):
    contracted = 25 - start_session
    enrollment = SimpleNamespace(
        id=91,
        student_id=student_id,
        class_id=10,
        status="ACTIVE",
        start_date=date(2026, 10, 1),
        end_date=None,
        enrolled_from_session=start_session,
        enrolled_until_session=24,
        planned_sessions=contracted,
        unit_fee=Decimal("150000"),
        agreed_course_fee=Decimal("150000") * Decimal(contracted),
        discount_amount=Decimal("0"),
        billing_policy_version="attendance_v2",
        freezes=[],
    )
    enrollment.has_tuition_contract = True
    return enrollment


def test_historical_correction_allows_attendance_and_tuition_for_old_session():
    enrollment = _enrollment(1)
    teaching_session = _session(1)
    attendance = SimpleNamespace(
        session_id=1,
        student_id=7,
        status=AttendanceStatus.PRESENT.value,
    )
    teaching_session.attendances = [attendance]

    assert AttendanceService._enrollment_covers_session(
        enrollment,
        teaching_session,
    ) is True

    accrual = TuitionAccrualService.calculate_from_records(
        enrollment,
        [teaching_session],
        date(2026, 10, 31),
    )

    assert accrual.billable_session_numbers == (1,)
    assert accrual.net_accrued == Decimal("150000.0000")


def test_genuine_mid_course_join_rejects_attendance_and_tuition_before_range():
    enrollment = _enrollment(2)
    teaching_session = _session(1)

    assert AttendanceService._enrollment_covers_session(
        enrollment,
        teaching_session,
    ) is False

    accrual = TuitionAccrualService.calculate_from_records(
        enrollment,
        [teaching_session],
        date(2026, 10, 31),
    )

    assert accrual.billable_session_numbers == ()
    assert accrual.net_accrued == Decimal("0.0000")


def test_legacy_unresolved_enrollment_keeps_date_range_fallback():
    enrollment = SimpleNamespace(
        status="ACTIVE",
        start_date=date(2026, 10, 1),
        end_date=None,
        enrolled_from_session=None,
        enrolled_until_session=None,
    )

    assert AttendanceService._enrollment_covers_session(
        enrollment,
        _session(1),
    ) is True


def test_class_enrollment_ui_uses_canonical_pricing_dialog():
    source = (
        ROOT / "ui/class_workspace/class_enrollment_dialog.py"
    ).read_text(encoding="utf-8")

    assert "EnrollmentPricingDialog(" in source
    assert "enrollment_kwargs = pricing.enrollment_kwargs()" in source
    assert "**enrollment_kwargs" in source


def test_class_service_facade_forwards_explicit_enrollment_snapshot():
    source = (ROOT / "services/class_service.py").read_text(encoding="utf-8")

    assert "def preview_enrollment_pricing" in source
    assert ".preview_enrollment_pricing(class_id, **pricing_kwargs)" in source
    assert ".enroll(student_id, class_id, **enrollment_kwargs)" in source


def test_attendance_does_not_create_finance_side_effects():
    source = (
        ROOT / "services/attendance_service.py"
    ).read_text(encoding="utf-8").lower()

    assert "income_service" not in source
    assert "outstanding_service" not in source
    assert "finance_events" not in source
