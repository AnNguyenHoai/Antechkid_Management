from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.core.clock import Clock, reset_clock, set_clock
from centermanager.database.base import Base
from centermanager.models.class_fee_history import ClassFeeHistory
from centermanager.models.finance_period import FinancePeriod
from centermanager.repositories.class_repository import ClassRepository
from centermanager.services.class_service import ClassService
from centermanager.services.outstanding_service import OutstandingService


class _Provider:
    def __init__(self, period_repo=None):
        self.period_repo = period_repo

    def finance_periods(self, _):
        return self.period_repo


class _PeriodRepo:
    def __init__(self, config):
        self.config, self.calls = config, []

    def get_unique_effective(self, target):
        self.calls.append(target)
        return self.config


@pytest.fixture(autouse=True)
def _restore_clock():
    yield
    reset_clock()


def _outstanding_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src" / "centermanager" / "services" / "outstanding_service.py").read_text(
        encoding="utf-8"
    )


def test_fee_history_preserves_old_fee_after_later_change():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    service = ClassService(Session)

    set_clock(Clock(today_fn=lambda: date(2026, 9, 1)))
    row = service.create_class("Python", start_date=date(2026, 9, 1), fee=1_000_000)
    class_id = row.id

    set_clock(Clock(today_fn=lambda: date(2026, 10, 1)))
    service.update_class(class_id, fee=1_200_000)

    with Session() as session:
        repo = ClassRepository(session)
        assert repo.get_fee_version_for_date(class_id, date(2026, 9, 15)).fee == 1_000_000
        assert repo.get_fee_version_for_date(class_id, date(2026, 10, 15)).fee == 1_200_000
        assert [
            x.fee
            for x in session.query(ClassFeeHistory)
            .filter_by(class_id=class_id)
            .order_by(ClassFeeHistory.id)
        ] == [1_000_000, 1_200_000]


def test_outstanding_v2_no_longer_uses_class_fee_history_as_obligation():
    source = _outstanding_source()
    assert "TuitionAccrualService.calculate_from_records" in source
    assert "get_fee_version_for_date" not in source
    assert "ClassFeeHistory" not in source


def test_finance_period_is_reporting_context_not_tuition_formula():
    source = _outstanding_source()
    assert "FinancePeriod is retained" in source
    assert "only as an optional reporting/filter context" in source
    assert "finance_period_start=" not in source
    assert "aggregate_active_tuition_by_student_class" not in source


def test_unresolved_enrollment_contract_remains_explicit_without_fee_fallback():
    source = _outstanding_source()
    assert "TuitionAccrualUnresolvedError" in source
    assert 'return Decimal("0"), False' in source
    assert "tuition_configured=configured" in source
    assert "enrollment.class_.fee" not in source


def test_unique_clamped_period_resolution():
    config = FinancePeriod(
        id=3,
        effective_from=date(2026, 9, 15),
        effective_to=date(2026, 10, 31),
        duration_months=3,
        status=FinancePeriod.STATUS_ACTIVE,
    )
    repo = _PeriodRepo(config)
    service = object.__new__(OutstandingService)
    service._repository_provider = _Provider(period_repo=repo)
    assert service._resolve_period(object(), date(2026, 10, 1)) == (
        date(2026, 9, 15),
        date(2026, 10, 31),
    )


def test_payments_are_exact_enrollment_attribution_with_as_of_cutoff():
    source = _outstanding_source()
    assert "sum_active_tuition_for_enrollment" in source
    assert "enrollment_id" in source
    assert "as_of_date=as_of_date" in source
    assert "_load_payment_totals" not in source


def test_migration_extends_head_without_backdating_legacy_fee():
    root = Path(__file__).resolve().parents[1]
    source = (root / "migrations" / "versions" / "1e10a028_class_fee_history.py").read_text(encoding="utf-8")
    model_source = (root / "src" / "centermanager" / "models" / "class_fee_history.py").read_text(encoding="utf-8")
    assert 'revision = "1e10a028"' in source and 'down_revision = "1e10a027"' in source
    assert "_CUTOVER_DATE = date(2026, 9, 24)" in source
    assert "NEVER project it backward" in source
    assert 'server_default="CLASS_FEE_CHANGE"' in source
    assert 'source="MIGRATION_BASELINE"' in source
    assert "event.listens_for" not in model_source
