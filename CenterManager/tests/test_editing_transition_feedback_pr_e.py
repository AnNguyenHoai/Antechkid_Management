# -*- coding: utf-8 -*-
"""PR-E source-level guardrails for inline editing transition feedback."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "src" / "centermanager" / "ui" / "application_shell.py"


def _source() -> str:
    return SHELL.read_text(encoding="utf-8")


def test_editing_transition_feedback_is_inline_and_indeterminate() -> None:
    source = _source()
    assert "EditingActivityIndicator" in source
    assert "QTimer(self)" in source
    assert "_ACTIVITY_FRAMES" in source
    assert "Preparing edit access…" in source
    assert "Saving and syncing changes…" in source
    assert "progress" not in source.lower().split("# ---- UI-PROD-07 feedback API ----", 1)[0] or "percentage" in source


def test_routine_editing_does_not_use_feedback_host_operation_row() -> None:
    source = _source()
    operation = source.split("def _run_edit_operation", 1)[1].split("def set_mode", 1)[0]
    assert "begin_operation(" not in operation
    assert "finish_operation(" not in operation
    assert "_start_activity" in operation
    assert "_stop_activity" in operation


def test_animation_is_presentation_only_and_preserves_write_signals() -> None:
    source = _source()
    assert "start_edit_requested = Signal()" in source
    assert "finish_edit_requested = Signal()" in source
    assert "signal.emit()" in source
    assert "git " not in source.lower()
    assert "sqlite3" not in source
