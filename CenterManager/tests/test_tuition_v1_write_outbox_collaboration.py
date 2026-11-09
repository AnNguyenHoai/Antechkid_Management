"""Regression gates for Tuition V1 SQLCipher WRITE and RV-02 collaboration.

These tests use the same table-level permission mapping and recovery summary
validator as production; do not weaken collaboration or bypass WRITE ownership.
"""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager import models  # noqa: F401
from centermanager.database.base import Base
from centermanager.database.mutation_permissions import mutation_permissions
from centermanager.models.class_ import Class
from centermanager.models.monthly_tuition import MonthlyClassDefaultRecord
from centermanager.services.monthly_class_schedule_service import MonthlyClassScheduleService
from centermanager.services.recovery_change_outbox import (
    RecoveryOutboxError,
    _safe_summary_args,
)
import centermanager.services.monthly_class_schedule_service as schedule_module


def test_monthly_default_table_supports_create_class_write():
    """New class + its MONTHLY policy share a single SQLCipher transaction."""
    assert "class.create" in mutation_permissions("monthly_class_defaults", 18)
    assert "class.update" in mutation_permissions("monthly_class_defaults", 23)
    assert "lesson.create" in mutation_permissions("monthly_class_defaults", 23)
    assert mutation_permissions("nonexistent_monthly_table", 18) == ()


def test_monthly_term_table_supports_new_enrollment_and_explicit_opt_in():
    """Standard enrollment may insert a term without the manager override."""
    permissions = mutation_permissions("enrollment_monthly_tuition_terms", 18)
    assert "student.update" in permissions
    assert "class.update" in permissions
    assert "tuition.enrollment.override" in permissions


def test_monthly_schedule_outbox_uses_only_approved_metadata(monkeypatch):
    """Exercise the real monthly scheduling service and strict RV-02 sanitizer."""
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    observed = []
    try:
        with factory() as db:
            db.add(Class(
                name="Monthly collaboration fixture",
                status="ACTIVE", start_date=date(2026, 11, 1),
                end_date=date(2026, 11, 30), planned_sessions=10,
                sessions_per_week=2,
            ))
            db.flush()
            db.add(MonthlyClassDefaultRecord(
                class_id=1, monthly_fee_vnd=700000,
                effective_month=date(2026, 11, 1),
                created_at=datetime(2026, 11, 1),
                created_by="manager",
            ))
            db.commit()

        monkeypatch.setattr(
            schedule_module, "get_current_user",
            lambda: SimpleNamespace(username="manager"),
        )

        def checked_record(session, **kwargs):
            observed.append(kwargs)
            _safe_summary_args(kwargs["summary_args"])

        monkeypatch.setattr(schedule_module, "record_for_active_write", checked_record)
        monkeypatch.setattr(schedule_module, "mirror_after_successful_commit", lambda session: None)
        service = MonthlyClassScheduleService(factory)
        created = MonthlyClassScheduleService.create_month_sessions.__wrapped__(
            service, 1, date(2026, 11, 1), (5, 6),
        )
        assert created == 9
        assert len(observed) == 1
        assert observed[0]["summary_args"] == {"class_id": 1, "changed_count": 9}

        # Idempotent repeat creates no new recovery outbox mutation.
        assert MonthlyClassScheduleService.create_month_sessions.__wrapped__(
            service, 1, date(2026, 11, 1), (5, 6),
        ) == 9
        assert len(observed) == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("bad", [
    {"month": "2026-11-01"},
    {"count": 9},
    {"freeform_note": "secret"},
])
def test_recovery_outbox_rejects_unauthorized_metadata(bad):
    with pytest.raises(RecoveryOutboxError):
        _safe_summary_args(bad)
