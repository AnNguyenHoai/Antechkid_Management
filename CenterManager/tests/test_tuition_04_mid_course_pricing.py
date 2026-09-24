from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.enrollment_service import EnrollmentService, EnrollmentValidationError
from centermanager.services.permission_service import PermissionDeniedError


class _Provider:
    def __init__(self, class_obj, sessions=None):
        self._class_repo = MagicMock()
        self._class_repo.get_by_id.return_value = class_obj
        self._session_repo = MagicMock()
        self._session_repo.get_by_class.return_value = list(sessions or [])
        self._student_repo = MagicMock()
        self._student_repo.get_by_id.return_value = SimpleNamespace(id=7, deleted_at=None)
        self._enrollment_repo = MagicMock()
        self._enrollment_repo.exists.return_value = False
        self._enrollment_repo.get_active_by_class.return_value = []

    def classes(self, _session):
        return self._class_repo

    def sessions(self, _session):
        return self._session_repo

    def students(self, _session):
        return self._student_repo

    def enrollments(self, _session):
        return self._enrollment_repo


def _session_factory(session):
    context = MagicMock()
    context.__enter__.return_value = session
    context.__exit__.return_value = None
    return MagicMock(return_value=context)


def _class():
    return SimpleNamespace(
        id=10,
        name="Python A",
        course="Python",
        capacity=None,
        start_date=date(2026, 9, 1),
        deleted_at=None,
        has_course_contract=True,
        course_fee=3_600_000,
        planned_sessions=24,
    )


def _session(number, status):
    return SimpleNamespace(session_number=number, status=status)


def test_preview_resolves_mid_course_after_last_completed_session():
    provider = _Provider(
        _class(),
        sessions=[
            *[_session(number, SessionStatus.COMPLETED.value) for number in range(1, 9)],
            _session(9, SessionStatus.SCHEDULED.value),
            _session(10, SessionStatus.POSTPONED.value),
        ],
    )
    service = EnrollmentService(_session_factory(MagicMock()), repository_provider=provider)

    preview = service.preview_enrollment_pricing(10)

    assert preview["enrolled_from_session"] == 9
    assert preview["enrolled_until_session"] == 24
    assert preview["planned_sessions"] == 16
    assert preview["unit_fee"] == Decimal("150000.0000")
    assert preview["suggested_agreed_course_fee"] == Decimal("2400000.0000")
    assert preview["resolution"] == "AFTER_LAST_COMPLETED_SESSION"


def test_preview_starts_at_one_when_no_session_has_completed():
    provider = _Provider(
        _class(),
        sessions=[_session(1, SessionStatus.SCHEDULED.value)],
    )
    service = EnrollmentService(_session_factory(MagicMock()), repository_provider=provider)

    preview = service.preview_enrollment_pricing(10)

    assert preview["enrolled_from_session"] == 1
    assert preview["planned_sessions"] == 24
    assert preview["suggested_agreed_course_fee"] == Decimal("3600000.0000")
    assert preview["resolution"] == "NO_COMPLETED_SESSIONS"


def test_preview_rejects_join_after_all_planned_sessions_completed():
    provider = _Provider(
        _class(),
        sessions=[
            _session(number, SessionStatus.COMPLETED.value)
            for number in range(1, 25)
        ],
    )
    service = EnrollmentService(_session_factory(MagicMock()), repository_provider=provider)

    with pytest.raises(EnrollmentValidationError, match="already completed all planned sessions"):
        service.preview_enrollment_pricing(10)


def test_explicit_start_session_keeps_deterministic_remaining_price():
    provider = _Provider(_class())
    service = EnrollmentService(_session_factory(MagicMock()), repository_provider=provider)

    preview = service.preview_enrollment_pricing(10, enrolled_from_session=23)

    assert preview["planned_sessions"] == 2
    assert preview["suggested_agreed_course_fee"] == Decimal("300000.0000")
    assert preview["resolution"] == "EXPLICIT"


def test_fee_override_requires_admin_capability_and_reason():
    session = MagicMock()
    provider = _Provider(_class())
    audit = MagicMock()
    service = EnrollmentService(
        _session_factory(session),
        repository_provider=provider,
        audit_service=audit,
    )
    non_admin = SimpleNamespace(
        id=2,
        username="manager",
        role=SimpleNamespace(name="manager"),
        is_active=True,
        permissions=set(),
    )

    with pytest.raises(PermissionDeniedError):
        service.enroll(
            7,
            10,
            enrolled_from_session=9,
            agreed_course_fee_override=2_000_000,
            override_reason="Approved scholarship",
            actor=non_admin,
        )

    admin = SimpleNamespace(
        id=1,
        username="admin",
        role=SimpleNamespace(name="admin"),
        is_active=True,
        permissions=set(),
    )
    with pytest.raises(EnrollmentValidationError, match="reason is required"):
        service.enroll(
            7,
            10,
            enrolled_from_session=9,
            agreed_course_fee_override=2_000_000,
            actor=admin,
        )


def test_admin_override_is_snapshotted_and_audited_in_transaction():
    session = MagicMock()
    provider = _Provider(_class())
    audit = MagicMock()

    def assign_id():
        enrollment = provider._enrollment_repo.add.call_args.args[0]
        enrollment.id = 55

    provider._enrollment_repo.flush.side_effect = assign_id
    service = EnrollmentService(
        _session_factory(session),
        repository_provider=provider,
        audit_service=audit,
    )
    admin = SimpleNamespace(
        id=1,
        username="admin",
        role=SimpleNamespace(name="admin"),
        is_active=True,
        permissions=set(),
    )

    enrollment = service.enroll(
        7,
        10,
        enrolled_from_session=9,
        agreed_course_fee_override=2_000_000,
        override_reason="Sibling discount exception",
        actor=admin,
    )

    assert enrollment.enrolled_from_session == 9
    assert enrollment.enrolled_until_session == 24
    assert enrollment.planned_sessions == 16
    assert enrollment.agreed_course_fee == Decimal("2000000.0000")
    assert enrollment.unit_fee == Decimal("125000.0000")
    provider._enrollment_repo.flush.assert_called_once()
    audit.record_in_session.assert_called_once()
    call = audit.record_in_session.call_args
    assert call.kwargs["action"] == "TUITION_ENROLLMENT_FEE_OVERRIDE"
    assert call.kwargs["target_id"] == 55
    assert call.kwargs["details"]["suggested_agreed_course_fee"] == "2400000.0000"
    assert call.kwargs["details"]["overridden_agreed_course_fee"] == "2000000.0000"
    assert call.kwargs["details"]["reason"] == "Sibling discount exception"
    session.commit.assert_called_once()


def test_enrollment_ui_requires_pricing_preview_before_save():
    from pathlib import Path

    widget = Path("src/centermanager/ui/student_workspace/enrollment_widget.py").read_text(encoding="utf-8")
    dialog = Path("src/centermanager/ui/student_workspace/enrollment_pricing_dialog.py").read_text(encoding="utf-8")

    assert "EnrollmentPricingDialog" in widget
    assert "pricing.enrollment_kwargs()" in widget
    assert "preview_enrollment_pricing" in dialog
    assert "TUITION_ENROLLMENT_OVERRIDE" in dialog
    assert "A reason is required for a fee override." in dialog
