# -*- coding: utf-8 -*-
"""UI-PROD-03 Application Shell V2 contract tests."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from centermanager.ui.application_shell import ApplicationTopBar, Breadcrumbs
from centermanager.ui.design_system.tokens import COMPONENT_METRICS
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import NavItem, WorkspaceNavigation
import centermanager.ui.application_shell as application_shell_module
import centermanager.ui.main_window as main_window_module
import centermanager.ui.workspace_header as workspace_header_module
import centermanager.ui.workspace_navigation as workspace_navigation_module


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


def test_shell_metrics_are_token_owned():
    required = {
        "app_top_bar_height",
        "workspace_sidebar_width",
        "workspace_sidebar_header_height",
        "page_header_height",
        "nav_indicator_width",
    }
    assert required.issubset(COMPONENT_METRICS)
    assert COMPONENT_METRICS["app_top_bar_height"] > 0
    assert COMPONENT_METRICS["workspace_sidebar_width"] > 0


def test_application_top_bar_contract(app):
    top_bar = ApplicationTopBar(
        user_name="Nguyen An",
        role_name="Admin",
        runtime_version="v1.2.3",
        sync_status="idle",
    )
    assert top_bar.height() == COMPONENT_METRICS["app_top_bar_height"]
    assert top_bar.user_label.text() == "Nguyen An"
    assert top_bar.role_label.text() == "Admin"
    assert top_bar.version_label.text() == "Runtime: v1.2.3"
    assert top_bar.sync_label.text() == "Sync: idle"

    top_bar.set_mode("WRITE", "success")
    top_bar.set_editor_state("You are editing", "success")
    top_bar.set_transaction_text("Editing")
    assert top_bar.mode_label.text() == "Mode: WRITE"
    assert top_bar.waiting_indicator.text() == "You are editing"
    assert top_bar.tx_state_label.text() == "Editing"


def test_top_bar_edit_actions_emit(app):
    top_bar = ApplicationTopBar(user_name="User")
    observed = []
    top_bar.start_edit_requested.connect(lambda: observed.append("start"))
    top_bar.finish_edit_requested.connect(lambda: observed.append("finish"))
    top_bar.cancel_edit_requested.connect(lambda: observed.append("cancel"))

    top_bar.start_edit_btn.click()
    top_bar.finish_edit_btn.setVisible(True)
    top_bar.finish_edit_btn.click()
    top_bar.cancel_btn.setVisible(True)
    top_bar.cancel_btn.click()
    assert observed == ["start", "finish", "cancel"]


def test_breadcrumbs_and_page_header_keep_navigation_contract(app):
    header = WorkspaceHeader("Student Workspace", "Dashboard")
    assert isinstance(header.breadcrumbs, Breadcrumbs)
    assert header.page_title_label.text() == "Dashboard"
    assert header.context_label.text() == "Student Workspace / Dashboard"

    observed = []
    header.back_home_clicked.connect(lambda: observed.append("home"))
    header.home_btn.click()
    assert observed == ["home"]

    header.set_context("Student Workspace", "Students")
    assert header.page_title_label.text() == "Students"
    assert header.context_label.text() == "Student Workspace / Students"


def test_sidebar_is_text_first_and_preserves_page_signal(app):
    navigation = WorkspaceNavigation(
        "Student Workspace",
        [
            {"id": "dashboard", "icon": "legacy-icon", "label": "Dashboard"},
            {"id": "students", "icon": "legacy-icon", "label": "Students"},
        ],
    )
    assert navigation.width() == COMPONENT_METRICS["workspace_sidebar_width"]
    assert all(isinstance(button, NavItem) for button in navigation._buttons)
    assert navigation._buttons[0].text() == "Dashboard"
    assert "legacy-icon" not in navigation._buttons[0].text()

    observed = []
    navigation.page_selected.connect(observed.append)
    navigation._buttons[1].click()
    assert observed == ["students"]

    navigation.set_active_page("dashboard")
    assert navigation._buttons[0].isChecked()


def test_shell_source_has_no_raw_hex_colors():
    for module in (
        application_shell_module,
        workspace_header_module,
        workspace_navigation_module,
        main_window_module,
    ):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert re.findall(r"#[0-9a-fA-F]{3,8}\b", source) == []


def test_main_window_is_wired_to_application_top_bar():
    source = Path(main_window_module.__file__).read_text(encoding="utf-8")
    assert "ApplicationTopBar(" in source
    assert "self.app_top_bar" in source
    assert "self.central_stack = QStackedWidget" in source
    assert "status_bar.addPermanentWidget" not in source
