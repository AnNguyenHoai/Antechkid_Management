# -*- coding: utf-8 -*-
"""Regression coverage for UI-PROD-07 Feedback & State UX."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from centermanager.ui.design_system.feedback import (  # noqa: E402
    FeedbackController,
    FeedbackRequest,
    FeedbackTone,
)


def test_feedback_request_requires_action_id_for_action_label() -> None:
    with pytest.raises(ValueError, match="action_id"):
        FeedbackRequest(message="Retry available", action_label="Retry")


def test_feedback_request_rejects_negative_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_ms"):
        FeedbackRequest(message="Saved", timeout_ms=-1)


def test_controller_projects_semantic_feedback() -> None:
    controller = FeedbackController()
    received = []
    controller.feedback_requested.connect(received.append)

    request = controller.success("Saved successfully", key="save-student")

    assert received == [request]
    assert request.tone is FeedbackTone.SUCCESS
    assert request.key == "save-student"


def test_operation_guard_prevents_duplicate_submit_and_requires_matching_token() -> None:
    controller = FeedbackController()
    events = []
    controller.busy_changed.connect(lambda *args: events.append(args))

    assert controller.begin_operation("publish", "Publishing changes…") is True
    assert controller.is_busy is True
    assert controller.begin_operation("second", "Duplicate") is False
    assert controller.finish_operation("wrong-token") is False
    assert controller.is_busy is True
    assert controller.finish_operation("publish") is True
    assert controller.is_busy is False

    assert events == [
        (True, "publish", "Publishing changes…"),
        (False, "publish", ""),
    ]


def test_save_flow_projects_saving_then_saved() -> None:
    controller = FeedbackController()
    busy_events = []
    feedback = []
    controller.busy_changed.connect(lambda *args: busy_events.append(args))
    controller.feedback_requested.connect(feedback.append)

    assert controller.begin_save("student-save") is True
    saved = controller.save_succeeded("student-save", key="student:42")

    assert saved is feedback[-1]
    assert saved is not None
    assert saved.message == "Saved ✓"
    assert saved.tone is FeedbackTone.SUCCESS
    assert busy_events == [
        (True, "student-save", "Saving…"),
        (False, "student-save", ""),
    ]


def test_delete_feedback_can_offer_undo_action() -> None:
    controller = FeedbackController()

    request = controller.deleted(
        message="Student deleted",
        undo_action_id="student:42:restore",
        key="student:42:delete",
    )

    assert request.tone is FeedbackTone.SUCCESS
    assert request.action_label == "Undo"
    assert request.action_id == "student:42:restore"
    assert request.timeout_ms == 7000


def test_system_error_does_not_leak_raw_exception_text() -> None:
    controller = FeedbackController()
    technical = RuntimeError("postgresql://secret-password@internal-db")

    request = controller.system_error(technical)

    assert request.tone is FeedbackTone.DANGER
    assert "secret-password" not in request.message
    assert request.message == "We couldn't complete this action. Please try again."


def test_persistent_severity_policy_and_transient_success_policy_are_explicit() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "design_system"
        / "feedback.py"
    ).read_text(encoding="utf-8")

    assert "FeedbackTone.SUCCESS: 3500" in source
    assert "FeedbackTone.INFO: 4500" in source
    assert "FeedbackTone.WARNING: 0" in source
    assert "FeedbackTone.DANGER: 0" in source


def test_application_shell_owns_one_feedback_host_and_preserves_legacy_aliases() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "application_shell.py"
    ).read_text(encoding="utf-8")

    assert "self.feedback_controller = feedback_controller or FeedbackController(self)" in source
    assert "self.feedback_host = FeedbackHost(self.feedback_controller, parent=self)" in source
    assert "self.tx_state_label = self.transaction_label" in source
    assert "self.start_edit_btn = self.start_edit_button" in source
    assert "self.finish_edit_btn = self.finish_edit_button" in source
    assert "self.cancel_btn = self.cancel_edit_button" in source


def test_confirmation_is_design_system_dialog_not_message_box() -> None:
    source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "design_system"
        / "feedback.py"
    ).read_text(encoding="utf-8")

    assert "class ConfirmationDialog(Dialog):" in source
    assert "QMessageBox" not in source
    assert "DesignSystemConfirmationDialog" not in source
    assert "self.cancel_button.setDefault(True)" in source
    assert "self.primary_button.setAutoDefault(False)" in source


def test_product_state_patterns_cover_search_permission_loading_and_readonly() -> None:
    state_source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "design_system"
        / "state_patterns.py"
    ).read_text(encoding="utf-8")
    foundation_source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "design_system"
        / "foundation.py"
    ).read_text(encoding="utf-8")
    form_source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "design_system"
        / "form_detail.py"
    ).read_text(encoding="utf-8")

    assert "class EmptySearchState(EmptyState):" in state_source
    assert "class PermissionState(StateView):" in state_source
    assert "class LoadingState(QWidget):" in foundation_source
    assert "skeleton_rows" in foundation_source
    assert '"readonly"' in form_source
    assert '"locked"' in form_source


def test_background_sync_remains_passive_shell_status_not_toast() -> None:
    shell_source = (
        Path(__file__).parents[1]
        / "src"
        / "centermanager"
        / "ui"
        / "application_shell.py"
    ).read_text(encoding="utf-8")

    assert 'self.sync_label.setText(f"Sync: {status}")' in shell_source
    sync_method = shell_source.split("def set_sync_status", 1)[1].split(
        "# ---- UI-PROD-07", 1
    )[0]
    assert "notify_" not in sync_method
