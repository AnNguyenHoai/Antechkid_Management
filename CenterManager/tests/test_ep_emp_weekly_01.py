from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "centermanager"
MIGRATION = ROOT / "migrations" / "versions" / "1e10a023_weekly_work_registration.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_migration():
    spec = importlib.util.spec_from_file_location("ep_emp_weekly_01_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_weekly_migration_normalizes_to_monday():
    migration = _load_migration()
    assert migration._monday(date(2026, 9, 21)) == date(2026, 9, 21)
    assert migration._monday(date(2026, 9, 27)) == date(2026, 9, 21)
    assert migration._monday("2026-10-01") == date(2026, 9, 28)


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["ACCEPTED", "ACCEPTED"], "ACCEPTED"),
        (["ACCEPTED", "SUBMITTED"], "SUBMITTED"),
        (["ACCEPTED", "DRAFT"], "DRAFT"),
    ],
)
def test_weekly_migration_keeps_least_final_state(statuses, expected):
    migration = _load_migration()
    rows = [
        {
            "status": status,
            "submitted_at": None,
            "accepted_at": None,
            "accepted_by_user_id": None,
        }
        for status in statuses
    ]
    status, *_ = migration._aggregate_registration_state(rows)
    assert status == expected


def test_migration_handles_month_boundary_without_duplicate_employee_week():
    source = _text(MIGRATION)
    assert "key = (source_reg[\"employee_id\"], ws)" in source
    assert "weekly_groups.setdefault" in source
    assert "uq_employee_work_registration_period_month" in source
    assert source.index("drop_constraint(\"uq_employee_work_registration_period_month\"") < source.index("periods.insert().values")
    assert "uq_employee_work_registration_period_week" in source
    assert "batch.drop_column(\"month\")" in source
    assert "batch.drop_column(\"year\")" in source


def test_service_contract_is_weekly_and_next_week_only():
    source = _text(SRC / "services" / "employee_work_registration_service.py")
    assert "def week_start(" in source
    assert "def next_week(" in source
    assert "def submit_week(" in source
    assert "def close_week(" in source
    assert "Only the next week can be submitted." in source
    assert "def close_month(" not in source
    assert "def next_month(" not in source


def test_admin_override_uses_week_start_not_year_month():
    source = _text(SRC / "services" / "employee_admin_management_service.py")
    assert "def reopen_period(" in source
    assert "week_start: date" in source
    assert "get_by_week_start(normalized)" in source
    assert '"week_start": normalized.isoformat()' in source
    assert "get_by_year_month" not in source


def test_manager_review_is_fully_week_scoped():
    source = _text(
        SRC / "ui" / "employee_workspace" / "employee_work_registration_review_page.py"
    )
    assert "self._rs.next_week()" in source
    assert "self._rs.get_period(self._week_start)" in source
    assert "self._rs.list_all(self._week_start)" in source
    assert "self._rs.close_week(self._week_start)" in source
    assert "self._admin_service.reopen_period(self._week_start" in source
    assert "next_month" not in source
    assert "close_month" not in source
    assert "Registration Month" not in source


def test_manager_detail_is_fully_week_scoped():
    source = _text(
        SRC / "ui" / "employee_workspace" / "employee_work_registration_detail_page.py"
    )
    assert "Registration week:" in source
    assert "period.week_start" in source
    assert "period.week_start + timedelta(days=6)" in source
    assert "self._rs.accept(self.registration.employee_id, self._week_start())" in source
    assert "self._rs.reopen(self.registration.employee_id, self._week_start())" in source
    assert "monthrange" not in source
    assert "period.month" not in source
    assert "period.year" not in source


def test_changed_python_files_compile():
    paths = [
        MIGRATION,
        SRC / "models" / "employee_work_registration.py",
        SRC / "models" / "employee_work_registration_period.py",
        SRC / "repositories" / "employee_work_registration_period_repository.py",
        SRC / "services" / "employee_work_registration_service.py",
        SRC / "services" / "employee_admin_management_service.py",
        SRC / "ui" / "employee_workspace" / "employee_work_registration_widget.py",
        SRC / "ui" / "employee_workspace" / "employee_work_registration_review_page.py",
        SRC / "ui" / "employee_workspace" / "employee_work_registration_detail_page.py",
    ]
    for path in paths:
        compile(_text(path), str(path), "exec")
