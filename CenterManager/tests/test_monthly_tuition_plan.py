from datetime import date

import pytest

from centermanager.services.monthly_tuition_plan import (
    PlanStatus, activate_monthly_plan, close_monthly_plan,
    preview_monthly_plan, revise_draft,
)


def sample():
    return preview_monthly_plan(
        class_id=5, month=date(2026, 11, 1), monthly_fee_vnd=800_000,
        schedule_version="weekly-sat-sun-v1",
        session_dates=[date(2026, 11, 1), date(2026, 11, 7)],
    )


def test_preview_activation_and_close_are_immutable():
    draft = sample()
    active = activate_monthly_plan(draft)
    closed = close_monthly_plan(active)
    assert draft.status == PlanStatus.DRAFT
    assert active.status == PlanStatus.ACTIVE
    assert closed.status == PlanStatus.CLOSED
    assert active.allocations == draft.allocations
    with pytest.raises(ValueError):
        revise_draft(active, session_dates=[date(2026, 11, 1)])
    with pytest.raises(ValueError):
        activate_monthly_plan(active)
    with pytest.raises(ValueError):
        close_monthly_plan(closed)


def test_draft_revision_bumps_version_without_mutating_original():
    old = sample()
    new = revise_draft(old, session_dates=[date(2026, 11, 1)])
    assert old.version == 1 and len(old.allocations) == 2
    assert new.version == 2 and new.allocations[0].amount_vnd == 800_000


def test_preview_rejects_wrong_month():
    with pytest.raises(ValueError):
        preview_monthly_plan(
            class_id=5, month=date(2026, 11, 1), monthly_fee_vnd=800_000,
            schedule_version="v1", session_dates=[date(2026, 12, 1)]
        )
