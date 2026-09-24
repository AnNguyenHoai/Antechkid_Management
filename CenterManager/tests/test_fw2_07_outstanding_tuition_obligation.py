from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

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


class _FeeRepo:
    def __init__(self, fee): self.fee, self.queries = fee, []
    def get_fee_version_for_date(self, class_id, on_date):
        self.queries.append((class_id, on_date))
        return None if self.fee is None else SimpleNamespace(fee=self.fee)

class _Provider:
    def __init__(self, class_repo=None, period_repo=None, income_repo=None):
        self.class_repo, self.period_repo, self.income_repo = class_repo, period_repo, income_repo
    def classes(self, _): return self.class_repo
    def finance_periods(self, _): return self.period_repo
    def incomes(self, _): return self.income_repo

class _PeriodRepo:
    def __init__(self, config): self.config, self.calls = config, []
    def get_unique_effective(self, target): self.calls.append(target); return self.config

class _IncomeRepo:
    def __init__(self, rows): self.rows, self.aggregate_calls = rows, []
    def aggregate_active_tuition_by_student_class(self, **kwargs):
        self.aggregate_calls.append(kwargs)
        grouped = {}
        for row in self.rows:
            key = (row.student_id, row.class_id)
            grouped[key] = grouped.get(key, 0) + row.amount
        return [(student_id, class_id, amount) for (student_id, class_id), amount in grouped.items()]

@pytest.fixture(autouse=True)
def _restore_clock():
    yield
    reset_clock()


def _enrollment(start=date(2026, 9, 15), end=None):
    return SimpleNamespace(
        student_id=11, class_id=7, start_date=start, end_date=end,
        class_=SimpleNamespace(id=7, name="Python", course="Python", start_date=date(2026, 9, 1), fee=1_200_000),
        student=SimpleNamespace(id=11, full_name="An", student_code="HS011"), course_name="Python",
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
        assert [x.fee for x in session.query(ClassFeeHistory).filter_by(class_id=class_id).order_by(ClassFeeHistory.id)] == [1_000_000, 1_200_000]


def test_one_fee_per_canonical_period_and_overlap_billability():
    repo = _FeeRepo(1_200_000)
    service = object.__new__(OutstandingService); service._repository_provider = _Provider(class_repo=repo)
    dto = service._calculate_from_enrollment(object(), _enrollment(), date(2026, 9, 15), date(2026, 12, 14), payment_totals={(11, 7): 200_000})
    assert dto.expected_tuition == 1_200_000 and dto.outstanding == 1_000_000
    assert service._calculate_from_enrollment(object(), _enrollment(start=date(2026, 12, 15)), date(2026, 9, 15), date(2026, 12, 14), payment_totals={}) is None


def test_midperiod_enrollment_uses_first_billable_date_fee_version():
    repo = _FeeRepo(900_000)
    service = object.__new__(OutstandingService); service._repository_provider = _Provider(class_repo=repo)
    service._calculate_from_enrollment(object(), _enrollment(start=date(2026, 10, 1)), date(2026, 9, 15), date(2026, 10, 14), payment_totals={})
    assert repo.queries == [(7, date(2026, 10, 1))]


def test_pre_cutover_fee_without_history_remains_unconfigured():
    repo = _FeeRepo(None)
    service = object.__new__(OutstandingService); service._repository_provider = _Provider(class_repo=repo)
    dto = service._calculate_from_enrollment(
        object(),
        _enrollment(),
        date(2026, 9, 15),
        date(2026, 10, 14),
        payment_totals={},
    )
    assert dto.expected_tuition == 0
    assert dto.tuition_configured is False


def test_unique_clamped_period_resolution():
    config = FinancePeriod(id=3, effective_from=date(2026, 9, 15), effective_to=date(2026, 10, 31), duration_months=3, status=FinancePeriod.STATUS_ACTIVE)
    repo = _PeriodRepo(config)
    service = object.__new__(OutstandingService); service._repository_provider = _Provider(period_repo=repo)
    assert service._resolve_period(object(), date(2026, 10, 1)) == (date(2026, 9, 15), date(2026, 10, 31))


def test_only_active_tuition_income_in_selected_period_reduces_obligation():
    income_repo = _IncomeRepo([SimpleNamespace(student_id=11, class_id=7, amount=100_000), SimpleNamespace(student_id=11, class_id=7, amount=200_000)])
    service = object.__new__(OutstandingService); service._repository_provider = _Provider(income_repo=income_repo)
    assert service._load_payment_totals(object(), date(2026, 9, 15), date(2026, 10, 14)) == {(11, 7): 300_000}
    assert income_repo.aggregate_calls == [{
        "income_type": "Tuition",
        "finance_period_start": date(2026, 9, 15),
        "date_from": date(2026, 9, 15),
        "date_to": date(2026, 10, 14),
        "student_id": None,
        "class_id": None,
    }]


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
