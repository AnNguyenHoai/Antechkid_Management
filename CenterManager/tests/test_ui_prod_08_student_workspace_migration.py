# -*- coding: utf-8 -*-
"""Regression contract for UI-PROD-08 Student Workspace migration."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "centermanager" / "ui"


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def assert_parses(relative: str) -> str:
    text = source(relative)
    ast.parse(text, filename=relative)
    return text


def test_student_workspace_migrated_sources_parse() -> None:
    for relative in (
        "student_workspace/student_workspace_shell.py",
        "student_workspace/student_list_page.py",
        "student_workspace/student_detail_page.py",
        "student_workspace/enrollment_widget.py",
        "student_workspace/student_attendance_widget.py",
        "student_workspace/student_financial_widget.py",
        "student_workspace/student_analytics_page.py",
        "students/student_form_dialog.py",
    ):
        assert_parses(relative)


def test_student_list_uses_v2_table_states_feedback_and_confirmation() -> None:
    text = assert_parses("student_workspace/student_list_page.py")
    for expected in ("DataTable", "SearchToolbar", "BulkActionBar", "EmptySearchState", "EditStateBanner", "ConfirmationDialog", "system_error"):
        assert expected in text
    assert "QMessageBox" not in text


def test_student_form_uses_canonical_save_flow_and_inline_validation() -> None:
    text = assert_parses("students/student_form_dialog.py")
    for expected in ("FormSection", "FormField", "begin_save", "Saving…", "save_succeeded", "Student saved ✓", "full_name_field.set_error"):
        assert expected in text
    assert "QMessageBox" not in text


def test_student_detail_uses_v2_tabs_detail_sections_and_content_states() -> None:
    text = assert_parses("student_workspace/student_detail_page.py")
    for expected in ("Tabs(", "DetailSection", "EditStateBanner", "EmptyState", "ErrorState", "ConfirmationDialog"):
        assert expected in text
    assert "QTabWidget" not in text
    assert "QMessageBox" not in text


def test_enrollment_uses_design_system_and_safe_transition_feedback() -> None:
    text = assert_parses("student_workspace/enrollment_widget.py")
    for expected in ("Card(", "Badge.from_status", "EditStateBanner", "ConfirmationDialog", "Enrollment completed", "Enrollment withdrawn"):
        assert expected in text
    assert "QMessageBox" not in text


def test_attendance_uses_data_table_loading_empty_and_error_states() -> None:
    text = assert_parses("student_workspace/student_attendance_widget.py")
    for expected in ("DataTable", "set_loading(True)", "set_error(", "system_error"):
        assert expected in text
    assert "QMessageBox" not in text


def test_student_finance_stays_read_only_and_permission_aware() -> None:
    text = assert_parses("student_workspace/student_financial_widget.py")
    for expected in ("PermissionState", "DataTable", "OutstandingService", "IncomeService", "FinancePeriodService", "finance.view"):
        assert expected in text
    for forbidden in ("create_income(", "update_income(", "delete_income("):
        assert forbidden not in text
    assert "QMessageBox" not in text


def test_student_shell_reuses_application_feedback_and_routes_retry_actions() -> None:
    text = assert_parses("student_workspace/student_workspace_shell.py")
    for expected in ("app_top_bar", "feedback_controller", "feedback_host", "action_triggered"):
        assert expected in text
    for action_id in (
        "student-list-refresh",
        "student-detail-refresh",
        "student-enrollment-refresh",
        "student-attendance-refresh",
        "student-analytics-refresh",
    ):
        assert action_id in text


def test_background_sync_remains_passive() -> None:
    text = assert_parses("student_workspace/student_workspace_shell.py")
    tree = ast.parse(text)
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_on_sync_completed")
    fragment = ast.get_source_segment(text, method) or ""
    assert "refresh_current_student" in fragment
    assert "_feedback." not in fragment


def test_student_analytics_uses_shared_feedback_instead_of_message_box() -> None:
    text = assert_parses("student_workspace/student_analytics_page.py")
    assert "FeedbackController" in text
    assert "student-analytics-refresh" in text
    assert "QMessageBox" not in text
