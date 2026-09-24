from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from centermanager.models.class_ import Class
from centermanager.services.class_service import ClassService, ClassValidationError


def test_class_course_contract_derives_unit_fee_without_persisted_arithmetic():
    class_obj = Class(
        name="Python Basic K01",
        start_date=date(2026, 10, 1),
        course_fee=3_600_000,
        duration_months=3,
        planned_sessions=24,
        sessions_per_week=2,
    )

    assert class_obj.has_course_contract is True
    assert class_obj.unit_fee == Decimal("150000")


def test_unit_fee_is_decimal_and_does_not_assume_four_weeks_per_month():
    class_obj = Class(
        name="Course",
        start_date=date(2026, 10, 1),
        course_fee=1_000_000,
        duration_months=3,
        planned_sessions=7,
        sessions_per_week=2,
    )

    assert class_obj.unit_fee == Decimal(1_000_000) / Decimal(7)
    assert class_obj.planned_sessions == 7


def test_historical_class_without_session_contract_is_explicitly_unresolved():
    class_obj = Class(name="Legacy", fee=3_600_000, course_fee=3_600_000)

    assert class_obj.has_course_contract is False
    assert class_obj.unit_fee is None


@pytest.mark.parametrize(
    "kwargs, message",
    [
        (
            dict(
                start_date=None,
                course_fee=3_600_000,
                duration_months=3,
                planned_sessions=24,
                sessions_per_week=2,
            ),
            "Start date",
        ),
        (
            dict(
                start_date=date(2026, 10, 1),
                course_fee=-1,
                duration_months=3,
                planned_sessions=24,
                sessions_per_week=2,
            ),
            "Course fee",
        ),
        (
            dict(
                start_date=date(2026, 10, 1),
                course_fee=3_600_000,
                duration_months=0,
                planned_sessions=24,
                sessions_per_week=2,
            ),
            "Duration months",
        ),
        (
            dict(
                start_date=date(2026, 10, 1),
                course_fee=3_600_000,
                duration_months=3,
                planned_sessions=0,
                sessions_per_week=2,
            ),
            "Planned sessions",
        ),
        (
            dict(
                start_date=date(2026, 10, 1),
                course_fee=3_600_000,
                duration_months=3,
                planned_sessions=24,
                sessions_per_week=0,
            ),
            "Sessions per week",
        ),
    ],
)
def test_complete_course_contract_validation(kwargs, message):
    with pytest.raises(ClassValidationError, match=message):
        ClassService._validate_course_contract(require_complete=True, **kwargs)


def test_complete_course_contract_accepts_real_course_example():
    ClassService._validate_course_contract(
        start_date=date(2026, 10, 1),
        course_fee=3_600_000,
        duration_months=3,
        planned_sessions=24,
        sessions_per_week=2,
        require_complete=True,
    )


def test_legacy_unresolved_contract_remains_readable_during_migration():
    # No duration/session evidence existed historically, so compatibility mode
    # accepts an unresolved row instead of inventing values.
    ClassService._validate_course_contract(
        start_date=None,
        course_fee=3_600_000,
        duration_months=None,
        planned_sessions=None,
        sessions_per_week=None,
        require_complete=False,
    )


def test_migration_copies_recorded_fee_but_does_not_infer_session_metadata():
    source = Path(
        "migrations/versions/1e10a030_class_course_contract.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "1e10a029"' in source
    assert "SET course_fee = fee" in source
    assert 'Column("duration_months"' in source
    assert 'Column("planned_sessions"' in source
    assert 'Column("sessions_per_week"' in source

    # Historical duration/session data must remain unresolved; no arithmetic
    # backfill such as months * 4 * sessions/week is permitted.
    assert "duration_months * 4" not in source
    assert "sessions_per_week * 4" not in source
    assert "planned_sessions =" not in source.split("op.execute", 1)[1]


def test_academic_contract_source_has_no_finance_period_dependency():
    model_source = Path("src/centermanager/models/class_.py").read_text(encoding="utf-8")
    service_source = Path("src/centermanager/services/class_service.py").read_text(encoding="utf-8")

    for source in (model_source, service_source):
        assert "FinancePeriod" not in source
        assert "finance_period" not in source
