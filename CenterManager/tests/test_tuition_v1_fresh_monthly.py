"""Production-mode fresh monthly class: first month, fees, and safety gates."""
from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager import models  # noqa: F401
from centermanager.models.class_ import Class
from centermanager.models.student import Student
from centermanager.models.enrollment import Enrollment
from centermanager.models.monthly_tuition import (
    MonthlyClassDefaultRecord, EnrollmentMonthlyTuitionTerm,
    MonthlyTuitionPlanRecord, MonthlyTuitionAllocationRecord,
)
from centermanager.services.monthly_class_schedule_service import (
    MonthlyClassScheduleError, MonthlyClassScheduleService, month_dates,
)
from centermanager.services.monthly_tuition_plan_store import (
    MonthlyPlanStorageError, MonthlyTuitionPlanStore,
)
from centermanager.services.monthly_tuition_quote_service import MonthlyTuitionQuoteService
from centermanager.services.enrollment_service import EnrollmentService, EnrollmentValidationError

import centermanager.services.monthly_class_schedule_service as schedule_module
import centermanager.services.monthly_tuition_plan_store as plan_module
import centermanager.services.enrollment_service as enrollment_module


@pytest.fixture()
def monthly_factory(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    actor = SimpleNamespace(username="admin")
    monkeypatch.setattr(schedule_module, "get_current_user", lambda: actor)
    monkeypatch.setattr(plan_module, "get_current_user", lambda: actor)
    monkeypatch.setattr(enrollment_module, "get_current_user", lambda: actor)
    for module in (schedule_module, plan_module, enrollment_module):
        monkeypatch.setattr(module, "record_for_active_write", lambda *a, **kw: None)
        monkeypatch.setattr(module, "mirror_after_successful_commit", lambda *a, **kw: None)
    monkeypatch.setattr(plan_module, "get_clock", lambda: SimpleNamespace(today=lambda: date(2026, 11, 9)))
    with factory() as db:
        klass = Class(
            name="K2 Python monthly", start_date=date(2026, 11, 1),
            end_date=date(2027, 2, 28), status="ACTIVE",
            course_fee=0, fee=0, duration_months=4,
            planned_sessions=40, sessions_per_week=2,
        )
        student = Student(student_code="FRESH-001", full_name="Synthetic learner")
        db.add_all((klass, student))
        db.flush()
        db.add(MonthlyClassDefaultRecord(
            class_id=klass.id, monthly_fee_vnd=700000,
            effective_month=date(2026, 11, 1),
            created_at=datetime(2026, 11, 9),
            created_by="admin",
        ))
        db.commit()
    yield factory
    engine.dispose()


def test_november_2026_weekend_has_nine_original_sessions():
    result = month_dates(date(2026, 11, 1), None, date(2026, 11, 1), (5, 6))
    assert len(result) == 9
    assert result[0] == date(2026, 11, 1)
    assert result[-1] == date(2026, 11, 29)


def test_fresh_monthly_requires_full_schedule_before_draft(monthly_factory):
    plan = MonthlyTuitionPlanStore(monthly_factory)
    with pytest.raises(MonthlyPlanStorageError, match="weekly schedule"):
        MonthlyTuitionPlanStore.create_draft.__wrapped__(
            plan, 1, date(2026, 11, 1), 700000, "weekly:5,6"
        )


def test_new_month_schedule_is_immutable_and_monthly_plan_is_exact(monthly_factory):
    schedule = MonthlyClassScheduleService(monthly_factory)
    count = MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    assert count == 9
    # Repeat clicks must not create duplicate billable lessons.
    assert MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    ) == count
    with pytest.raises(MonthlyClassScheduleError, match="fixed"):
        MonthlyClassScheduleService.create_month_sessions.__wrapped__(
            schedule, 1, date(2026, 12, 1), (4, 5)
        )
    plan = MonthlyTuitionPlanStore(monthly_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        plan, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(plan, pid)
    with monthly_factory() as db:
        allocations = db.scalars(select(MonthlyTuitionAllocationRecord).where(
            MonthlyTuitionAllocationRecord.plan_id == pid
        )).all()
        assert len(allocations) == 9
        assert sum(a.amount_vnd for a in allocations) == 700000
        assert db.get(MonthlyTuitionPlanRecord, pid).status == "ACTIVE"


def test_fresh_monthly_enrollment_inherits_term_without_migration(monthly_factory):
    schedule = MonthlyClassScheduleService(monthly_factory)
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    plan = MonthlyTuitionPlanStore(monthly_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        plan, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(plan, pid)
    service = EnrollmentService(monthly_factory)
    student = service.enroll(1, 1, start_date=date(2026, 11, 9))
    with monthly_factory() as db:
        rows = db.scalars(select(EnrollmentMonthlyTuitionTerm).where(
            EnrollmentMonthlyTuitionTerm.enrollment_id == student.id
        )).all()
        assert len(rows) == 1
        assert rows[0].effective_from == date(2026, 11, 1)
        assert db.get(Enrollment, student.id).start_date == date(2026, 11, 9)
    quote = MonthlyTuitionQuoteService(monthly_factory).quote(
        student.id, date(2026, 11, 1), 1
    )
    assert quote.amount_vnd > 0
    assert quote.amount_vnd < 700000  # New learner joins after first 3 sessions.


def test_monthly_enrollment_fails_closed_without_activated_plan(monthly_factory):
    with pytest.raises(EnrollmentValidationError, match="activate"):
        EnrollmentService(monthly_factory).enroll(
            1, 1, start_date=date(2026, 11, 9)
        )
    with monthly_factory() as db:
        assert db.query(EnrollmentMonthlyTuitionTerm).count() == 0
        assert db.query(Enrollment).count() == 0


def test_previous_month_stays_blocked_even_for_new_class(monthly_factory):
    schedule = MonthlyClassScheduleService(monthly_factory)
    with pytest.raises(MonthlyClassScheduleError):
        MonthlyClassScheduleService.create_month_sessions.__wrapped__(
            schedule, 1, date(2026, 10, 1), (5, 6)
        )


def test_migration_new_schema_contract():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "1e10a047_monthly_class_defaults.py"
    text = path.read_text(encoding="utf-8")
    assert 'down_revision = "1e10a046"' in text
    assert 'monthly_class_defaults' in text


def test_production_class_dialog_offers_monthly_without_exposing_legacy_uat():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui"
    dialog = (root / "class_workspace" / "class_form_dialog.py").read_text(encoding="utf-8")
    assert 'addItem("Theo tháng (lớp mới)", "MONTHLY")' in dialog
    assert 'kwargs["monthly_fee_vnd"]' in dialog
    detail = (root / "class_workspace" / "class_detail_page.py").read_text(encoding="utf-8")
    assert 'or monthly_policy is not None' in detail


def test_new_class_creation_persists_monthly_default_atomically(monkeypatch):
    from datetime import timedelta
    import centermanager.services.class_service as class_module
    from centermanager.services.class_service import ClassService
    from centermanager.core.clock import get_clock

    today = get_clock().today()
    first = today.replace(day=1)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(class_module, "get_current_user", lambda: SimpleNamespace(username="admin"))
    monkeypatch.setattr(class_module, "record_for_active_write", lambda *a, **kw: None)
    monkeypatch.setattr(class_module, "mirror_after_successful_commit", lambda *a, **kw: None)
    try:
        service = ClassService(factory)
        monthly = service.create_class(
            "New monthly", start_date=first, end_date=first + timedelta(days=90),
            course_fee=0, duration_months=4, planned_sessions=40, sessions_per_week=2,
            monthly_fee_vnd=700000, monthly_effective_month=first,
        )
        assert service.get_monthly_class_default(monthly.id) == (700000, first)
        legacy = service.create_class(
            "Old style", start_date=first, end_date=first + timedelta(days=90),
            course_fee=2800000, duration_months=4, planned_sessions=32, sessions_per_week=2,
        )
        assert service.get_monthly_class_default(legacy.id) is None
        with factory() as db:
            assert db.query(MonthlyClassDefaultRecord).count() == 1
    finally:
        engine.dispose()


def test_monthly_policy_rejects_dual_legacy_fee(monkeypatch):
    from datetime import timedelta
    from centermanager.services.class_service import ClassService, ClassValidationError
    from centermanager.core.clock import get_clock
    today = get_clock().today()
    first = today.replace(day=1)
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    try:
        with pytest.raises(ClassValidationError, match="legacy course fee"):
            ClassService(factory).create_class(
                "Invalid dual pricing", start_date=first, end_date=first + timedelta(days=90),
                course_fee=2800000, duration_months=4, planned_sessions=40,
                sessions_per_week=2, monthly_fee_vnd=700000, monthly_effective_month=first,
            )
        with factory() as db:
            assert db.query(Class).count() == 0
    finally:
        engine.dispose()


def test_backfill_november_1_preserves_full_monthly_tuition(monthly_factory):
    schedule = MonthlyClassScheduleService(monthly_factory)
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    store = MonthlyTuitionPlanStore(monthly_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(store, pid)
    onboarding = __import__(
        "centermanager.services.class_service", fromlist=["ClassService"]
    ).ClassService(monthly_factory)
    preview = onboarding.preview_new_monthly_enrollment(1, date(2026, 11, 1))
    assert preview["planned_sessions"] == 9
    assert preview["remaining_sessions"] == 9
    assert preview["first_month_amount_vnd"] == 700000
    enrollment = EnrollmentService(monthly_factory).enroll(
        1, 1, start_date=date(2026, 11, 1), enrolled_from_session=1
    )
    quote = MonthlyTuitionQuoteService(monthly_factory).quote(
        enrollment.id, date(2026, 11, 1), 1
    )
    assert quote.amount_vnd == 700000
    assert quote.lines[0].chargeable_sessions == 9


def test_backfill_november_9_bills_only_remaining_original_sessions(monthly_factory):
    schedule = MonthlyClassScheduleService(monthly_factory)
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    store = MonthlyTuitionPlanStore(monthly_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(store, pid)
    from centermanager.services.class_service import ClassService
    preview = ClassService(monthly_factory).preview_new_monthly_enrollment(
        1, date(2026, 11, 9)
    )
    assert preview["remaining_sessions"] == 6
    enrollment = EnrollmentService(monthly_factory).enroll(
        1, 1, start_date=date(2026, 11, 9), enrolled_from_session=1
    )
    quote = MonthlyTuitionQuoteService(monthly_factory).quote(
        enrollment.id, date(2026, 11, 1), 1
    )
    assert quote.amount_vnd == preview["first_month_amount_vnd"]
    assert quote.lines[0].chargeable_sessions == 6


def test_backfill_onboarding_ui_exposes_date_and_does_not_use_legacy_override():
    from pathlib import Path
    path = (
        Path(__file__).resolve().parents[1] / "src" / "centermanager"
        / "ui" / "student_workspace" / "enrollment_pricing_dialog.py"
    )
    source = path.read_text(encoding="utf-8")
    assert "self._monthly_policy = self._service.get_monthly_class_default(" in source
    assert "self.monthly_start_date = QDateEdit(self)" in source
    assert "preview_new_monthly_enrollment(" in source
    assert '"start_date": self.monthly_start_date.date().toPython()' in source
    assert '"enrolled_from_session": 1' in source


def test_monthly_class_onboarding_rejects_before_class_start(monthly_factory):
    from centermanager.services.class_service import ClassService, ClassValidationError
    with pytest.raises(ClassValidationError, match="outside"):
        ClassService(monthly_factory).preview_new_monthly_enrollment(
            1, date(2026, 10, 31)
        )
    with pytest.raises(EnrollmentValidationError):
        EnrollmentService(monthly_factory).enroll(
            1, 1, start_date=date(2026, 10, 31), enrolled_from_session=1
        )


def test_multi_class_fresh_db_can_activate_november_sequentially(monthly_factory):
    """Founder can input one class and students at a time, not pre-build all."""
    schedule = MonthlyClassScheduleService(monthly_factory)
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    store = MonthlyTuitionPlanStore(monthly_factory)
    first = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(store, first)
    EnrollmentService(monthly_factory).enroll(
        1, 1, start_date=date(2026, 11, 1), enrolled_from_session=1
    )
    with monthly_factory() as db:
        second = Class(
            name="K3 Python", start_date=date(2026, 11, 1),
            end_date=date(2027, 2, 28), status="ACTIVE",
            course_fee=0, duration_months=4, planned_sessions=40,
            sessions_per_week=2,
        )
        db.add(second)
        db.flush()
        second_id = second.id
        db.add(MonthlyClassDefaultRecord(
            class_id=second_id, monthly_fee_vnd=800000,
            effective_month=date(2026, 11, 1),
            created_at=datetime(2026, 11, 9), created_by="admin",
        ))
        db.commit()
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, second_id, date(2026, 11, 1), (5, 6)
    )
    second_draft = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, second_id, date(2026, 11, 1), 800000, "weekly:5,6"
    )
    MonthlyTuitionPlanStore.activate.__wrapped__(store, second_draft)
    with monthly_factory() as db:
        assert db.get(MonthlyTuitionPlanRecord, second_draft).status == "ACTIVE"


def test_fresh_month_bootstrap_rejects_mixed_legacy_class(monthly_factory):
    with monthly_factory() as db:
        db.add(Class(
            name="Historical legacy class", status="ACTIVE",
            start_date=date(2025, 11, 1), course_fee=2000000,
            duration_months=4, planned_sessions=32, sessions_per_week=2,
        ))
        db.commit()
    schedule = MonthlyClassScheduleService(monthly_factory)
    MonthlyClassScheduleService.create_month_sessions.__wrapped__(
        schedule, 1, date(2026, 11, 1), (5, 6)
    )
    store = MonthlyTuitionPlanStore(monthly_factory)
    draft = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2026, 11, 1), 700000, "weekly:5,6"
    )
    with pytest.raises(MonthlyPlanStorageError, match="all-monthly"):
        MonthlyTuitionPlanStore.activate.__wrapped__(store, draft)
