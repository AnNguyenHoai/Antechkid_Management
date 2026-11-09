from datetime import date

import pytest

from centermanager.services.monthly_tuition_ledger_projection import (
    SessionBillingEvent, SessionBillingOutcome,
    allocate_by_session_id, project_enrollment_month,
)


def test_same_date_sessions_allocate_deterministically():
    rows = [(2, date(2026, 11, 1)), (1, date(2026, 11, 1)), (3, date(2026, 11, 3))]
    expected = allocate_by_session_id(800_000, rows)
    assert [row.session_id for row in expected] == [1, 2, 3]
    assert sum(row.amount_vnd for row in expected) == 800_000
    assert expected == allocate_by_session_id(800_000, reversed(rows))


def test_midmonth_and_center_cancellation_and_prepay():
    rows = allocate_by_session_id(800_000, [
        (1, date(2026, 11, 1)), (2, date(2026, 11, 7)), (3, date(2026, 11, 8)),
    ])
    result = project_enrollment_month(
        enrollment_id=10, effective_from=date(2026, 11, 7),
        as_of_date=date(2026, 11, 30), allocations=rows,
        events=[SessionBillingEvent(2, SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP)],
        cash_received_vnd=800_000,
    )
    assert result.gross_vnd == rows[1].amount_vnd + rows[2].amount_vnd
    assert result.cancelled_vnd == rows[1].amount_vnd
    assert result.earned_vnd == rows[2].amount_vnd
    assert result.outstanding_vnd == 0
    assert result.prepaid_vnd == 800_000 - rows[2].amount_vnd


def test_as_of_future_cash_is_not_unearned_tuition():
    rows = allocate_by_session_id(800_000, [(1, date(2026, 11, 15))])
    value = project_enrollment_month(
        enrollment_id=10, effective_from=date(2026, 11, 1),
        as_of_date=date(2026, 11, 8), allocations=rows, cash_received_vnd=800_000)
    assert value.earned_vnd == 0 and value.prepaid_vnd == 800_000


def test_cancel_no_makeup_cannot_double_credit():
    rows = allocate_by_session_id(800_000, [(1, date(2026, 11, 1))])
    event = SessionBillingEvent(1, SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP)
    with pytest.raises(ValueError):
        project_enrollment_month(
            enrollment_id=10, effective_from=date(2026, 11, 1),
            as_of_date=date(2026, 11, 30), allocations=rows, events=[event, event])


def test_reschedule_preserves_tuition_and_student_absence_does_not_create_credit():
    rows = allocate_by_session_id(800_000, [(1, date(2026, 11, 1))])
    result = project_enrollment_month(
        enrollment_id=10, effective_from=date(2026, 11, 1),
        as_of_date=date(2026, 11, 30), allocations=rows,
        events=[SessionBillingEvent(1, SessionBillingOutcome.RESCHEDULED)])
    assert result.outstanding_vnd == 800_000


@pytest.mark.parametrize("pairs", [[], [(1, date(2026, 11, 1)), (1, date(2026, 11, 2))],
    [(1, date(2026, 11, 1)), (2, date(2026, 12, 1))]])
def test_invalid_allocation_rejected(pairs):
    with pytest.raises(ValueError):
        allocate_by_session_id(800_000, pairs)
