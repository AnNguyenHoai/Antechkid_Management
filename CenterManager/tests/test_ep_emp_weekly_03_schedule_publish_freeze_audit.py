# -*- coding: utf-8 -*-
"""EP-EMP-WEEKLY-03 regression tests for schedule publish/freeze/audit."""
from datetime import date
from pathlib import Path

import pytest

from centermanager.models.employee_schedule import EmployeeScheduleWeek
from centermanager.services.employee_schedule_service import (
    EmployeeScheduleService,
    EmployeeScheduleValidationError,
)


ROOT = Path(__file__).resolve().parent.parent
SERVICE = ROOT / "src" / "centermanager" / "services" / "employee_schedule_service.py"
UI = ROOT / "src" / "centermanager" / "ui" / "employee_workspace" / "employee_schedule_widget.py"
MIGRATION = ROOT / "migrations" / "versions" / "1e10a025_schedule_publish_freeze_audit.py"


def _week(status=EmployeeScheduleWeek.STATUS_DRAFT, version=1):
    return EmployeeScheduleWeek(
        id=1,
        week_start=date(2026, 9, 21),
        status=status,
        version=version,
    )


def test_week_lifecycle_contract_and_official_visibility():
    draft = _week()
    assert draft.week_end == date(2026, 9, 27)
    assert draft.is_official is False
    assert draft.is_locked is False

    published = _week(EmployeeScheduleWeek.STATUS_PUBLISHED)
    assert published.is_official is True
    assert published.is_locked is True

    frozen = _week(EmployeeScheduleWeek.STATUS_FROZEN)
    assert frozen.is_official is True
    assert frozen.is_locked is True
    assert EmployeeScheduleWeek.VALID_STATUSES == {"DRAFT", "PUBLISHED", "FROZEN"}


def test_only_draft_week_is_mutable():
    assert EmployeeScheduleService._require_draft(_week()).status == "DRAFT"
    for status in (EmployeeScheduleWeek.STATUS_PUBLISHED, EmployeeScheduleWeek.STATUS_FROZEN):
        with pytest.raises(EmployeeScheduleValidationError, match="locked"):
            EmployeeScheduleService._require_draft(_week(status))


def test_service_exposes_publish_freeze_override_and_employee_official_read_boundary():
    source = SERVICE.read_text(encoding="utf-8")
    assert "def publish_week(" in source
    assert "def freeze_week(" in source
    assert "def reopen_week_for_override(" in source
    assert "def list_official_employee_week(" in source
    assert "def employee_week_state(" in source
    assert "self._require_draft(repo.get_or_create_week(ws))" in source
    assert "An override reason is required." in source
    assert "week.version += 1" in source
    assert "WEEKLY_SCHEDULE_PUBLISHED" in source
    assert "WEEKLY_SCHEDULE_FROZEN" in source
    assert "WEEKLY_SCHEDULE_REOPENED_FOR_OVERRIDE" in source


def test_publish_revalidates_every_assignment_against_accepted_availability():
    source = SERVICE.read_text(encoding="utf-8")
    assert "def _validate_publishable(" in source
    assert "Cannot publish an empty weekly schedule." in source
    assert "self._ensure_available(" in source
    assert "self._ensure_no_assignment_overlap(" in source
    publish = source[source.index("def publish_week("):source.index("def freeze_week(")]
    assert "self._validate_publishable(s, repo, week)" in publish


def test_employee_does_not_receive_draft_schedule_as_official():
    source = SERVICE.read_text(encoding="utf-8")
    official = source[source.index("def list_official_employee_week("):source.index("def employee_week_state(")]
    assert "if week is None or not week.is_official:" in official
    assert "return []" in official
    state = source[source.index("def employee_week_state("):source.index("def add_week_assignment(")]
    assert '"UNPUBLISHED"' in state


def test_ui_exposes_manager_lifecycle_actions_and_employee_official_schedule():
    source = UI.read_text(encoding="utf-8")
    assert 'QPushButton("Publish Entire Week")' in source
    assert 'QPushButton("Freeze Week")' in source
    assert 'QPushButton("Re-open for Override")' in source
    assert "self.service.list_official_employee_week" in source
    assert "self.service.publish_week(self._week_start)" in source
    assert "self.service.freeze_week(self._week_start)" in source
    assert "self.service.reopen_week_for_override(self._week_start, reason)" in source


def test_migration_adds_version_publish_and_freeze_metadata():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "1e10a025"' in source
    assert 'down_revision = "1e10a024"' in source
    for column in (
        "version",
        "published_at",
        "published_by_user_id",
        "frozen_at",
        "frozen_by_user_id",
    ):
        assert f'"{column}"' in source


def test_migration_head_contains_schedule_lifecycle_columns(migration_db_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect
    from centermanager.database.engine import create_engine_for_path

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{migration_db_path}")
    command.upgrade(cfg, "head")

    engine = create_engine_for_path(migration_db_path)
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("employee_schedule_weeks")
    }
    assert {
        "version",
        "published_at",
        "published_by_user_id",
        "frozen_at",
        "frozen_by_user_id",
    }.issubset(columns)
