"""Test authorised storage seam with isolated SQLite and no WRITE-runtime flags."""
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager import models  # noqa: F401
from centermanager.models.class_ import Class
from centermanager.models.session import Session
from centermanager.models.monthly_tuition import (
    MonthlyTuitionAllocationRecord, MonthlyTuitionPlanRecord,
)
from centermanager.services.monthly_tuition_plan_store import (
    MonthlyPlanStorageError, MonthlyTuitionPlanStore,
)
import centermanager.services.monthly_tuition_plan_store as module


@pytest.fixture()
def db_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        klass = Class(name="Test monthly class", status="ACTIVE")
        db.add(klass)
        db.flush()
        db.add_all([
            Session(class_id=klass.id, session_number=n, title=f"Lesson {n}",
                    scheduled_date=date(2040, 1, 1), status="Scheduled")
            for n in (1, 2)
        ])
        db.commit()
    yield factory
    engine.dispose()


def test_draft_snapshot_preserves_same_day_sessions(db_factory):
    store = MonthlyTuitionPlanStore(db_factory)
    preview = store.preview(1, date(2040, 1, 1), 800_000)
    assert [row.amount_vnd for row in preview] == [400_000, 400_000]
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2040, 1, 1), 800_000, "v1"
    )
    with db_factory() as db:
        plan = db.get(MonthlyTuitionPlanRecord, pid)
        rows = db.scalars(select(MonthlyTuitionAllocationRecord).where(
            MonthlyTuitionAllocationRecord.plan_id == pid)).all()
        assert plan.status == "DRAFT" and sum(r.amount_vnd for r in rows) == 800_000


def test_activation_requires_unchanged_session_snapshot(db_factory, monkeypatch):
    store = MonthlyTuitionPlanStore(db_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2040, 1, 1), 800_000, "v1"
    )
    monkeypatch.setattr(module, "get_current_user", lambda: SimpleNamespace(username="test_manager"))
    with db_factory() as db:
        db.add(Session(class_id=1, session_number=3, title="New session",
                       scheduled_date=date(2040, 1, 3), status="Scheduled"))
        db.commit()
    with pytest.raises(MonthlyPlanStorageError, match="planned sessions changed"):
        MonthlyTuitionPlanStore.activate.__wrapped__(store, pid)


def test_activation_creates_immutable_active_version(db_factory, monkeypatch):
    store = MonthlyTuitionPlanStore(db_factory)
    pid = MonthlyTuitionPlanStore.create_draft.__wrapped__(
        store, 1, date(2040, 1, 1), 800_000, "v1"
    )
    monkeypatch.setattr(module, "get_current_user", lambda: SimpleNamespace(username="test_manager"))
    MonthlyTuitionPlanStore.activate.__wrapped__(store, pid)
    with db_factory() as db:
        assert db.get(MonthlyTuitionPlanRecord, pid).status == "ACTIVE"
    with pytest.raises(MonthlyPlanStorageError):
        MonthlyTuitionPlanStore.activate.__wrapped__(store, pid)

def test_cancelled_planned_lesson_stays_in_original_allocation(db_factory):
    with db_factory() as db:
        first = db.query(Session).order_by(Session.id).first()
        first.status = "Cancelled"
        db.commit()
    preview = MonthlyTuitionPlanStore(db_factory).preview(1, date(2040, 1, 1), 800_000)
    assert len(preview) == 2
    assert sum(item.amount_vnd for item in preview) == 800_000
