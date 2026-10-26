# -*- coding: utf-8 -*-
"""Regression contracts for the global shell and dashboard facelift."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_application_shell_has_persistent_global_sidebar():
    main = _source("main_window.py")

    assert "from centermanager.ui.global_navigation import GlobalSidebar" in main
    assert "self.global_sidebar = GlobalSidebar(shell_body)" in main
    assert "self.global_sidebar.navigation_requested.connect(self._on_global_navigation)" in main
    assert "shell_body_layout.addWidget(self.global_sidebar)" in main
    assert "shell_body_layout.addWidget(self.central_stack, 1)" in main


def test_global_sidebar_exposes_center_and_workspace_navigation():
    sidebar = _source("global_navigation.py")

    assert '"home", "home", "Center overview"' in sidebar
    assert '"student", "student", "Student Workspace"' in sidebar
    assert '"teacher", "teacher", "Teacher Workspace"' in sidebar
    assert '"class", "class", "Class Workspace"' in sidebar
    assert '"finance", "finance", "Finance Workspace"' in sidebar
    assert '"employee", "employee", "Employee Workspace"' in sidebar
    assert '"settings", "settings", "Settings"' in sidebar
    assert '"reports", "reports", "Reports"' in sidebar
    assert "AppIcon" in sidebar
    assert "QPushButton:checked" in sidebar


def test_global_navigation_reuses_existing_workspace_routes():
    main = _source("main_window.py")

    assert 'if target == "home":' in main
    assert 'if target == "settings":' in main
    assert 'if target == "reports":' in main
    assert 'self.admin_workspace.navigate_to("settings")' in main
    assert 'self.student_workspace.navigate_to("analytics")' in main
    assert 'self.global_sidebar.set_active("student")' in main
    assert 'self.global_sidebar.set_active("class")' in main
    assert 'self.global_sidebar.set_active("finance")' in main


def test_home_dashboard_uses_operational_three_column_composition():
    home = _source("home/home_page.py")

    assert 'title = QLabel("Dashboard"' in home
    assert 'workspace_title = QLabel("Center operations"' in home
    assert "for column in range(3):" in home
    assert "self.workspace_grid.setColumnStretch(column, 1)" in home
    assert "row = index // 3" in home
    assert "column = index % 3" in home
    assert "self.workspace_grid.addWidget(card, row, column)" in home
    assert '"student": (0, 0, 2, 1, "featured")' not in home
    assert 'COLORS["state_warning_bg"] if object_name == "HomeAttentionPanel"' in home


def test_workspace_cards_support_visual_density_without_new_business_data():
    card = _source("home/workspace_card.py")

    assert 'variant: str = "regular"' in card
    assert 'self._variant = variant' in card
    assert 'self.setMinimumHeight(146)' in card
    assert 'self.setMaximumHeight(164)' in card
    assert 'self.icon_label = AppIcon(' in card
    assert 'self.description_label.setVisible(False)' in card
    assert 'self.action_btn = Button("Open →"' in card
    assert 'self._variant == "featured"' not in card
    assert 'self._variant == "compact"' not in card
