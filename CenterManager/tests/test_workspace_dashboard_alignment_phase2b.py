# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2B workspace dashboard alignment."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_metric_card_supports_semantic_vector_icons():
    metric = _source("shared/metric_card.py")
    app_icon = _source("app_icon.py")

    assert "from centermanager.ui.app_icon import AppIcon" in metric
    assert "if AppIcon.supports(icon):" in metric
    assert 'tile_color=icon_bg' in metric
    for name in (
        "check",
        "archive",
        "star",
        "calendar",
        "warning",
        "income",
        "expense",
        "assignment",
    ):
        assert f'"{name}":' in app_icon


def test_shared_activity_and_warning_components_accept_vector_icons():
    activity = _source("shared/activity_card.py")
    warning = _source("shared/warning_banner.py")

    assert "if AppIcon.supports(icon):" in activity
    assert "if AppIcon.supports(icon):" in warning
    assert 'tile_color=COLORS["blue_50"]' in activity
    assert "tile_color=fg" in warning


def test_student_dashboard_uses_semantic_icons_and_tones():
    source = _source("student_workspace/student_dashboard_page.py")

    assert '{"icon": "student", "label": "Total Students"' in source
    assert '{"icon": "check", "label": "Active"' in source
    assert '{"icon": "archive", "label": "Archived"' in source
    assert '{"icon": "star", "label": "New This Month"' in source
    assert '"tone": "success"' in source
    assert 'icon="warning"' in source
    assert 'PrimaryButton("Add Student")' in source
    assert 'PrimaryButton("➕ Add Student")' not in source


def test_class_dashboard_uses_existing_data_with_aligned_visual_language():
    source = _source("class_workspace/class_dashboard_page.py")

    assert '{"icon": "class", "label": "Total Classes"' in source
    assert '{"icon": "check", "label": "Active Classes"' in source
    assert '"label": "Students in Active Classes"' in source
    assert '{"icon": "calendar", "label": "Upcoming Sessions (7d)"' in source
    assert '"StudentEnrolled": "student"' in source
    assert '"ScheduleUpdated": "calendar"' in source


def test_teacher_dashboard_uses_semantic_icons_without_new_metrics():
    source = _source("teacher_workspace/teacher_dashboard_page.py")

    assert '{"icon": "teacher", "label": "Total Teachers"' in source
    assert '{"icon": "check", "label": "Active Teachers"' in source
    assert '{"icon": "assignment", "label": "Total Assignments"' in source
    assert '"TeacherAssigned": "assignment"' in source
    assert "total_assignments = for assigned_class in teacher.assigned_classes" in source


def test_finance_dashboard_uses_shared_controls_and_balanced_chart_row():
    source = _source("finance_workspace/finance_dashboard_page.py")

    assert "from centermanager.ui.shared import StatisticGrid, DataTable, LoadingWidget, ChartCard, SectionHeader" in source
    assert "ButtonVariant.GHOST" in source
    assert '{"icon": "income", "label": "Income Selected Period"' in source
    assert '{"icon": "expense", "label": "Expense Selected Period"' in source
    assert '{"icon": "warning", "label": "Outstanding Tuition"' in source
    assert 'payment_method_row.addWidget(self.revenue_method_chart, 1)' in source
    assert 'payment_method_row.addWidget(self.expense_method_chart, 1)' in source


def test_phase_2b_does_not_create_employee_dashboard_or_change_data_services():
    employee = _source("employee_workspace/employee_workspace_shell.py")

    assert "EmployeeDashboardPage" not in employee
    assert "Capability-aware Employee Workspace" in employee
