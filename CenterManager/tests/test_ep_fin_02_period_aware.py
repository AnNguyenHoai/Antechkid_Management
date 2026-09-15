from datetime import date
from pathlib import Path

from centermanager.dto.outstanding_dto import (
    OutstandingDTO,
    OUTSTANDING_STATUS_NOT_YET,
    OUTSTANDING_STATUS_PARTIAL,
    OUTSTANDING_STATUS_PAID,
    OUTSTANDING_STATUS_OVERPAID,
)
from centermanager.models.finance_period import FinancePeriodDefinition


def test_finance_period_boundaries_follow_configured_duration():
    anchor = date(2026, 1, 15)
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 1, 15), 1) == (
        date(2026, 1, 15),
        date(2026, 2, 14),
    )
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 2, 15), 1) == (
        date(2026, 2, 15),
        date(2026, 3, 14),
    )
    assert FinancePeriodDefinition.period_for_date(anchor, date(2026, 7, 20), 6) == (
        date(2026, 7, 15),
        date(2027, 1, 14),
    )


def test_outstanding_status_distinguishes_not_yet_partial_paid_and_overpaid():
    common = dict(
        student_id=1,
        student_name="Student",
        student_code="S001",
        class_id=2,
        class_name="Class",
        expected_tuition=1_000_000,
    )
    assert OutstandingDTO.create(**common, paid=0).status == OUTSTANDING_STATUS_NOT_YET
    assert OutstandingDTO.create(**common, paid=500_000).status == OUTSTANDING_STATUS_PARTIAL
    assert OutstandingDTO.create(**common, paid=1_000_000).status == OUTSTANDING_STATUS_PAID
    assert OutstandingDTO.create(**common, paid=1_200_000).status == OUTSTANDING_STATUS_OVERPAID


def test_finance_period_migration_is_unique_and_chained_after_ep_fin_01():
    versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    migration = versions / "1e10a019_income_finance_period.py"
    assert migration.exists()
    assert not (versions / "1e10a009_income_finance_period.py").exists()
    content = migration.read_text(encoding="utf-8")
    assert 'revision = "1e10a019"' in content
    assert 'down_revision = "1e10a018"' in content
