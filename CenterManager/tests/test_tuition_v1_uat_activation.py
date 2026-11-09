"""Tuition V1 local UAT gate: never expose experimental controls by default."""
from __future__ import annotations

from pathlib import Path

import pytest

from centermanager.services.tuition_v1_uat_gate import (
    UAT_ENV_NAME, tuition_v1_uat_enabled,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("0", False), ("true", False),
     ("yes", False), ("1 ", False), ("1", True)],
)
def test_tuition_v1_uat_gate_requires_exact_opt_in(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv(UAT_ENV_NAME, raising=False)
    else:
        monkeypatch.setenv(UAT_ENV_NAME, value)
    assert tuition_v1_uat_enabled() is expected


def test_uat_mode_never_replaces_verified_sqlcipher_opt_in():
    """UI cannot bypass the service's encrypted backup / WRITE safety gate."""
    from centermanager.services.monthly_tuition_enrollment_service import (
        MonthlyTuitionEnrollmentService,
    )
    from centermanager.services.monthly_tuition_verified_preflight import (
        VerifiedMonthlyTuitionPreflight,
    )
    assert MonthlyTuitionEnrollmentService.from_verified_backup is not None
    assert VerifiedMonthlyTuitionPreflight._backup_verified is not None
    source = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui" / "class_workspace" / "monthly_tuition_opt_in_dialog.py"
    code = source.read_text(encoding="utf-8")
    assert "MonthlyTuitionEnrollmentService.from_verified_backup(" in code
    assert "BackupService().create_backup(" in code
    assert "service.activate_future_month(" in code
    assert "tuition_v1_uat_enabled()" in code


def test_class_ui_gate_is_local_and_explicit():
    root = Path(__file__).resolve().parents[1] / "src" / "centermanager"
    code = (root / "ui" / "class_workspace" / "class_detail_page.py").read_text(encoding="utf-8")
    assert "_MONTHLY_TUITION_UI_ENABLED = tuition_v1_uat_enabled()" in code
    assert 'accepted.strip() != "UAT"' in code
    code = (root / "ui" / "class_workspace" / "monthly_tuition_plan_dialog.py").read_text(encoding="utf-8")
    assert "MonthlyTuitionOptInDialog(" in code
