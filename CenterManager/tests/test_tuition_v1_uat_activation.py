"""Tuition V1 local UAT gate: never expose experimental controls by default."""
from __future__ import annotations

from pathlib import Path

import pytest

from centermanager.services.tuition_v1_uat_gate import (
    UAT_ENV_NAME, tuition_v1_uat_enabled,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("0", False), ("true", False),
     ("yes", False), ("1 ", False), ("1", True)],
)
def test_tuition_v1_uat_gate_requires_exact_opt_in(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv(UAT_ENV_NAME, raising=False)
    else:
        monkeypatch.setenv(UAT_ENV_NAME, value)
    assert tuition_v1_uat_enabled() is expected


def test_uat_mode_never_replaces_verified_sqlcipher_opt_in():
    """UI cannot bypass the service's encrypted backup / WRITE safety gate."""
    from centermanager.services.monthly_tuition_enrollment_service import (
        MonthlyTuitionEnrollmentService,
    )
    from centermanager.services.monthly_tuition_verified_preflight import (
        VerifiedMonthlyTuitionPreflight,
    )
    assert MonthlyTuitionEnrollmentService.from_verified_backup is not None
    assert VerifiedMonthlyTuitionPreflight._backup_verified is not None
    source = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui" / "class_workspace" / "monthly_tuition_opt_in_dialog.py"
    code = source.read_text(encoding="utf-8")
    assert "MonthlyTuitionEnrollmentService.from_verified_backup(" in code
    assert "BackupService().create_backup(" in code
    assert "service.activate_future_month(" in code
    assert "tuition_v1_uat_enabled()" in code


def test_class_ui_gate_is_local_and_explicit():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    code = (root / "ui" / "class_workspace" / "class_detail_page.py").read_text(encoding="utf-8")
    assert "_MONTHLY_TUITION_UI_ENABLED = tuition_v1_uat_enabled()" in code
    assert 'accepted.strip() != "UAT"' in code
    code = (root / "ui" / "class_workspace" / "monthly_tuition_plan_dialog.py").read_text(encoding="utf-8")
    assert "MonthlyTuitionOptInDialog(" in code


def test_uat_dialog_does_not_access_repository_or_sqlalchemy():
    source = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui" / "class_workspace" / "monthly_tuition_opt_in_dialog.py"
    code = source.read_text(encoding="utf-8")
    assert "centermanager.repositories" not in code
    assert "self._factory()" not in code
    assert "self._service.list_class_enrollments(" in code


def test_uat_enrollment_selector_is_readonly_and_marks_activated_terms():
    from datetime import date, datetime
    from decimal import Decimal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from centermanager.database.base import Base
    from centermanager import models  # noqa: F401
    from centermanager.models.class_ import Class
    from centermanager.models.student import Student
    from centermanager.models.enrollment import Enrollment
    from centermanager.models.monthly_tuition import EnrollmentMonthlyTuitionTerm
    from centermanager.services.monthly_tuition_enrollment_service import MonthlyTuitionEnrollmentService

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    try:
        with factory() as db:
            klass = Class(name="UAT draft class", status="ACTIVE")
            student = Student(student_code="UAT-001", full_name="Synthetic Student")
            db.add_all((klass, student))
            db.flush()
            active = Enrollment(
                class_id=klass.id, student_id=student.id, status="ACTIVE",
                start_date=date(2040, 1, 1),
                agreed_course_fee=Decimal("800000"),
                planned_sessions=2, unit_fee=Decimal("400000"),
                enrolled_from_session=1, enrolled_until_session=2,
                discount_amount=Decimal("0"), billing_policy_version="attendance_v2",
            )
            db.add(active)
            db.flush()
            db.add(EnrollmentMonthlyTuitionTerm(
                enrollment_id=active.id, effective_from=date(2040, 2, 1),
                activated_at=datetime(2040, 1, 1), activated_by="uat_manager",
            ))
            db.commit()
            class_id, enrollment_id = klass.id, active.id
        selected = MonthlyTuitionEnrollmentService(factory).list_class_enrollments(class_id)
        assert selected == ((enrollment_id, "Synthetic Student", True),)
        with factory() as db:
            assert db.query(EnrollmentMonthlyTuitionTerm).count() == 1
    finally:
        engine.dispose()
