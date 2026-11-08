"""Phase 4 migration safety: run the additive revision on an isolated SQLite copy."""
from datetime import date
from decimal import Decimal
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session as DbSession

from centermanager.database.base import Base
from centermanager import models  # noqa: F401 - ensure all FKs present
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.models.session import Session
from centermanager.services.tuition_accrual_service import TuitionAccrualService


def _revision():
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "1e10a046_monthly_tuition_opt_in.py"
    spec = importlib.util.spec_from_file_location("tuition_v1_migration_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_additive_migration_keeps_legacy_contract_and_obligation():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    # Production already has all legacy tables. Recreate that shape here,
    # excluding only the four NEW tables created by the migration under test.
    new_tables = {
        "monthly_tuition_plans", "monthly_tuition_allocations",
        "enrollment_monthly_tuition_terms", "monthly_tuition_outcomes",
    }
    Base.metadata.create_all(
        engine,
        tables=[table for table in Base.metadata.sorted_tables
                if table.name not in new_tables],
    )
    with DbSession(engine) as db:
        klass = Class(name="Historic class", status="ACTIVE")
        db.add(klass)
        db.flush()
        enrollment = Enrollment(
            class_id=klass.id, student_id=9, status="ACTIVE",
            agreed_course_fee=Decimal("800000"), planned_sessions=2,
            unit_fee=Decimal("400000"), enrolled_from_session=1,
            enrolled_until_session=2, discount_amount=Decimal("0"),
            billing_policy_version="attendance_v2",
        )
        lessons = [
            Session(class_id=klass.id, session_number=n, title=f"Lesson {n}",
                    scheduled_date=date(2026, 10, n), status="Completed")
            for n in (1, 2)
        ]
        db.add_all([enrollment, *lessons])
        db.commit()
        before = TuitionAccrualService.calculate_from_records(
            enrollment, lessons, date(2026, 10, 31)
        ).net_accrued

    revision = _revision()
    with engine.begin() as conn:
        revision.op = Operations(MigrationContext.configure(conn))
        revision.upgrade()
    assert "monthly_tuition_plans" in inspect(engine).get_table_names()
    assert "enrollment_monthly_tuition_terms" in inspect(engine).get_table_names()
    with DbSession(engine) as db:
        enrollment = db.scalar(select(Enrollment))
        lessons = db.scalars(select(Session)).all()
        after = TuitionAccrualService.calculate_from_records(
            enrollment, lessons, date(2026, 10, 31)
        ).net_accrued
        assert before == after == Decimal("800000.0000")
        assert enrollment.billing_policy_version == "attendance_v2"
        assert db.execute(select(Enrollment)).scalars().first().id == enrollment.id
    engine.dispose()
