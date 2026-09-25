from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.tuition_accrual_service import (
    TuitionAccrualService,
    TuitionAccrualUnresolvedError,
)


def _enrollment(**overrides):
    values = dict(
        id=7,
        class_id=10,
        has_tuition_contract=True,
        planned_sessions=24,
        unit_fee=Decimal("150000.0000"),
        discount_amount=Decimal("0.0000"),
        enrolled_from_session=1,
        enrolled_until_session=24,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _session(number, status=SessionStatus.COMPLETED.value, scheduled=date(2026, 9, 1), actual=None):
    return SimpleNamespace(
        class_id=10,
        session_number=number,
        status=status,
        scheduled_date=scheduled,
        actual_date=actual,
    )


def test_ten_completed_sessions_accrue_1_500_000():
    sessions = [_session(i, scheduled=date(2026, 9, i)) for i in range(1, 11)]

    result = TuitionAccrualService.calculate_from_records(
        _enrollment(), sessions, date(2026, 9, 30)
    )

    assert result.planned_sessions == 24
    assert result.billable_sessions == 10
    assert result.billable_session_numbers == tuple(range(1, 11))
    assert result.unit_fee == Decimal("150000.0000")
    assert result.gross_accrued == Decimal("1500000.0000")
    assert result.discount == Decimal("0.0000")
    assert result.net_accrued == Decimal("1500000.0000")


@pytest.mark.parametrize(
    "status",
    [
        SessionStatus.SCHEDULED.value,
        SessionStatus.POSTPONED.value,
        SessionStatus.CANCELLED.value,
    ],
)
def test_non_completed_statuses_do_not_accrue(status):
    result = TuitionAccrualService.calculate_from_records(
        _enrollment(), [_session(1, status=status)], date(2026, 9, 30)
    )
    assert result.billable_sessions == 0
    assert result.gross_accrued == Decimal("0.0000")


def test_only_effective_enrollment_range_accrues():
    enrollment = _enrollment(
        planned_sessions=16,
        enrolled_from_session=9,
        enrolled_until_session=24,
    )
    sessions = [_session(i) for i in (8, 9, 10, 24)]

    result = TuitionAccrualService.calculate_from_records(
        enrollment, sessions, date(2026, 9, 30)
    )

    assert result.billable_session_numbers == (9, 10, 24)
    assert result.billable_sessions == 3
    assert result.gross_accrued == Decimal("450000.0000")


def test_as_of_date_prefers_actual_delivery_date():
    sessions = [
        _session(1, scheduled=date(2026, 9, 1), actual=date(2026, 9, 10)),
        _session(2, scheduled=date(2026, 9, 2), actual=date(2026, 9, 20)),
    ]

    result = TuitionAccrualService.calculate_from_records(
        _enrollment(), sessions, date(2026, 9, 15)
    )

    assert result.billable_session_numbers == (1,)


def test_as_of_date_falls_back_to_scheduled_date_when_actual_missing():
    result = TuitionAccrualService.calculate_from_records(
        _enrollment(),
        [_session(1, scheduled=date(2026, 9, 10), actual=None)],
        date(2026, 9, 10),
    )
    assert result.billable_sessions == 1


def test_contract_discount_accrues_proportionally_and_reconciles_at_completion():
    enrollment = _enrollment(discount_amount=Decimal("600000"))

    partial = TuitionAccrualService.calculate_from_records(
        enrollment,
        [_session(i) for i in range(1, 7)],
        date(2026, 9, 30),
    )
    assert partial.gross_accrued == Decimal("900000.0000")
    assert partial.discount == Decimal("150000.0000")
    assert partial.net_accrued == Decimal("750000.0000")

    complete = TuitionAccrualService.calculate_from_records(
        enrollment,
        [_session(i) for i in range(1, 25)],
        date(2026, 9, 30),
    )
    assert complete.gross_accrued == Decimal("3600000.0000")
    assert complete.discount == Decimal("600000.0000")
    assert complete.net_accrued == Decimal("3000000.0000")


def test_duplicate_session_records_cannot_double_accrue():
    duplicate = _session(1)
    result = TuitionAccrualService.calculate_from_records(
        _enrollment(), [duplicate, duplicate], date(2026, 9, 30)
    )
    assert result.billable_sessions == 1
    assert result.gross_accrued == Decimal("150000.0000")


def test_unresolved_legacy_enrollment_does_not_invent_accrual():
    with pytest.raises(TuitionAccrualUnresolvedError):
        TuitionAccrualService.calculate_from_records(
            _enrollment(has_tuition_contract=False),
            [_session(1)],
            date(2026, 9, 30),
        )


def test_repository_api_loads_enrollment_and_class_sessions():
    enrollment = _enrollment()
    enrollment_repo = MagicMock()
    enrollment_repo.get_by_id.return_value = enrollment
    session_repo = MagicMock()
    session_repo.get_by_class.return_value = [_session(1)]
    provider = MagicMock()
    provider.enrollments.return_value = enrollment_repo
    provider.sessions.return_value = session_repo
    db_session = MagicMock()
    context = MagicMock()
    context.__enter__.return_value = db_session
    context.__exit__.return_value = None

    service = TuitionAccrualService(MagicMock(return_value=context), provider)
    result = service.calculate(7, date(2026, 9, 30))

    enrollment_repo.get_by_id.assert_called_once_with(7)
    session_repo.get_by_class.assert_called_once_with(10)
    assert result.billable_sessions == 1


def test_accrual_service_has_no_finance_period_dependency():
    source = Path("src/centermanager/services/tuition_accrual_service.py").read_text(encoding="utf-8")
    lowered = source.lower()
    assert "finance_period" not in lowered
    assert "financeperiod" not in lowered
    assert "financialsettlement" not in lowered


def test_ui_and_outstanding_do_not_own_billable_session_policy():
    root = Path("src/centermanager")
    targets = list((root / "ui").rglob("*.py")) + [root / "services" / "outstanding_service.py"]
    for path in targets:
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        assert "BillableSessionPolicy" not in source, f"{path} must consume accrual service, not billing policy directly"
