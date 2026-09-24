from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from centermanager.ui.class_workspace.class_form_dialog import (
    _planned_end_date,
    _unit_fee,
)


FORM_PATH = Path("src/centermanager/ui/class_workspace/class_form_dialog.py")


def test_unit_fee_preview_uses_course_fee_over_explicit_planned_sessions():
    assert _unit_fee(3_600_000, 24) == Decimal("150000")
    assert _unit_fee(3_600_000, 0) is None


def test_planned_end_uses_calendar_months_not_four_week_assumption():
    assert _planned_end_date(date(2026, 9, 15), 3) == date(2026, 12, 14)
    assert _planned_end_date(date(2026, 1, 31), 1) == date(2026, 2, 27)


def test_class_form_defaults_start_date_from_application_clock():
    source = FORM_PATH.read_text(encoding="utf-8")
    assert "get_clock().today()" in source
    assert "QDate.currentDate" not in source


def test_class_form_projects_complete_course_contract_to_service():
    source = FORM_PATH.read_text(encoding="utf-8")
    for field in (
        "course_fee=course_fee",
        "duration_months=duration_months",
        "planned_sessions=planned_sessions",
        "sessions_per_week=sessions_per_week",
    ):
        assert field in source
    assert "fee=fee" not in source


def test_class_form_has_read_only_derived_preview_and_no_four_week_formula():
    source = FORM_PATH.read_text(encoding="utf-8")
    assert "Tuition / Session" in source
    assert "Planned End" in source
    assert "Course Summary" in source
    assert "_unit_fee(fee, planned)" in source
    assert "_planned_end_date(start, duration)" in source
    assert "* 4" not in source
    assert "4 *" not in source


def test_incomplete_migrated_class_can_preserve_unresolved_contract():
    source = FORM_PATH.read_text(encoding="utf-8")
    assert "Legacy class: course contract is incomplete" in source
    assert "if not self._course_contract_was_touched():" in source
    assert "return True" in source
    assert 'if self._course_contract_was_touched():' in source
