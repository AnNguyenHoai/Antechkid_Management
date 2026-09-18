from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from centermanager.models.finance_period import FinancePeriod
from centermanager.repositories.finance_period_repository import FinancePeriodRepository
from centermanager.services.finance_period_service import FinancePeriodService


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    FinancePeriod.__table__.create(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(
        "centermanager.services.finance_period_service.get_current_user",
        lambda: SimpleNamespace(is_admin=True),
    )


def _configure(service, duration_months, effective_from):
    return FinancePeriodService.configure.__wrapped__(
        service, duration_months, effective_from
    )


def _deactivate(service, period_id, effective_to):
    return FinancePeriodService.deactivate.__wrapped__(
        service, period_id, effective_to
    )


def test_forward_configuration_closes_previous_on_previous_day(session_factory, admin):
    service = FinancePeriodService(session_factory)
    first = _configure(service, 3, date(2026, 1, 1))
    second = _configure(service, 6, date(2026, 4, 1))

    with session_factory() as session:
        first_db = session.get(FinancePeriod, first.id)
        second_db = session.get(FinancePeriod, second.id)
        assert first_db.effective_to == date(2026, 3, 31)
        assert first_db.status == FinancePeriod.STATUS_INACTIVE
        assert second_db.effective_to is None
        assert second_db.status == FinancePeriod.STATUS_ACTIVE


def test_backdated_configuration_splits_historical_range_without_overlap(session_factory, admin):
    service = FinancePeriodService(session_factory)
    january = _configure(service, 3, date(2026, 1, 1))
    april = _configure(service, 6, date(2026, 4, 1))
    february = _configure(service, 1, date(2026, 2, 1))

    with session_factory() as session:
        repo = FinancePeriodRepository(session)
        january_db = session.get(FinancePeriod, january.id)
        february_db = session.get(FinancePeriod, february.id)
        april_db = session.get(FinancePeriod, april.id)

        assert january_db.effective_to == date(2026, 1, 31)
        assert february_db.effective_to == date(2026, 3, 31)
        assert april_db.effective_to is None
        assert february_db.status == FinancePeriod.STATUS_INACTIVE
        assert april_db.status == FinancePeriod.STATUS_ACTIVE

        assert repo.get_active(date(2026, 1, 31)).id == january.id
        assert repo.get_active(date(2026, 2, 1)).id == february.id
        assert repo.get_active(date(2026, 3, 31)).id == february.id
        assert repo.get_active(date(2026, 4, 1)).id == april.id


def test_duplicate_effective_date_is_rejected(session_factory, admin):
    service = FinancePeriodService(session_factory)
    _configure(service, 3, date(2026, 1, 1))

    with pytest.raises(ValueError, match="already exists"):
        _configure(service, 6, date(2026, 1, 1))


def test_deactivate_rejects_end_before_start(session_factory, admin):
    service = FinancePeriodService(session_factory)
    period = _configure(service, 3, date(2026, 4, 1))

    with pytest.raises(ValueError, match="earlier than effective_from"):
        _deactivate(service, period.id, date(2026, 3, 31))

    with session_factory() as session:
        stored = session.get(FinancePeriod, period.id)
        assert stored.status == FinancePeriod.STATUS_ACTIVE
        assert stored.effective_to is None


def test_deactivate_cannot_overlap_next_period(session_factory, admin):
    service = FinancePeriodService(session_factory)
    first = _configure(service, 3, date(2026, 1, 1))
    _configure(service, 6, date(2026, 4, 1))

    with pytest.raises(ValueError, match="next Finance period"):
        _deactivate(service, first.id, date(2026, 4, 1))


def test_database_rejects_inverted_effective_range(session_factory):
    with session_factory() as session:
        session.add(
            FinancePeriod(
                duration_months=3,
                status=FinancePeriod.STATUS_INACTIVE,
                effective_from=date(2026, 4, 1),
                effective_to=date(2026, 3, 31),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_integrity_migration_extends_current_single_head():
    source = Path("migrations/versions/1e10a020_finance_period_integrity.py").read_text(
        encoding="utf-8"
    )
    assert 'revision = "1e10a020"' in source
    assert 'down_revision = "1e10a019"' in source
    assert "ck_finance_period_effective_range" in source
    assert "latest-effective-from-wins" in source
