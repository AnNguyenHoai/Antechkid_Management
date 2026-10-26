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

    assert '"home", "⌂", "Center overview"' in sidebar
    assert '"student", "●", "Student Workspace"' in sidebar
    assert '"teacher", "✓", "Teacher Workspace"' in sidebar
    assert '"class", "◆", "Class Workspace"' in sidebar
    assert '"finance", "▣", "Finance Workspace"' in sidebar
    assert '"employee", "▤", "Employee Workspace"' in sidebar
    assert '"settings", "⚙", "Settings"' in sidebar
    assert '"reports", "▥", "Reports"' in sidebar
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
    assert "self.workspace_grid.setColumnStretch(0, 5)" in home
    assert "self.workspace_grid.setColumnStretch(1, 3)" in home
    assert "self.workspace_grid.setColumnStretch(2, 3)" in home
    assert '"student": (0, 0, 2, 1, "featured")' in home
    assert '"finance": (0, 2, 1, 1, "compact")' in home
    assert '"employee": (1, 2, 1, 1, "compact")' in home
    assert 'COLORS["state_warning_bg"] if object_name == "HomeAttentionPanel"' in home


def test_workspace_cards_support_visual_density_without_new_business_data():
    card = _source("home/workspace_card.py")

    assert 'variant: str = "regular"' in card
    assert 'self._variant = variant' in card
    assert 'self._variant == "featured"' in card
    assert 'self._variant == "compact"' in card
    assert 'self.icon_label = QLabel(self._icon or "•", self)' in card
    assert 'self.description_label.setVisible(self._variant != "compact")' in card
