# -*- coding: utf-8 -*-
"""Regression contract for UI-PROD-09 Desktop Production Polish."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMainWindow

from centermanager.ui.application_shell import ApplicationTopBar
from centermanager.ui.design_system.desktop import (
    ElidedLabel,
    apply_desktop_window_policy,
    desktop_stylesheet,
)
from centermanager.ui.design_system.tokens import TYPOGRAPHY
from centermanager.ui.workspace_header import WorkspaceHeader
import centermanager.ui.application_shell as application_shell_module
import centermanager.ui.design_system.desktop as desktop_module
import centermanager.ui.workspace_header as workspace_header_module


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


def test_elided_label_preserves_semantic_text_and_tooltip(app):
    full_text = "A deliberately long runtime status that must remain inspectable"
    label = ElidedLabel(full_text)
    label.resize(48, 24)
    label._refresh_display_text()

    assert label.text() == full_text
    assert label.toolTip() == full_text
    assert label.accessibleName() == full_text
    assert label.displayed_text() != full_text


def test_top_bar_uses_overflow_safe_labels_without_breaking_contract(app):
    top_bar = ApplicationTopBar(
        user_name="Nguyen Hoai An With A Very Long Display Name",
        role_name="Center Administrator",
        runtime_version="v2026.09.23-production",
        sync_status="synchronizing-with-remote-runtime",
    )

    for label in (
        top_bar.version_label,
        top_bar.sync_label,
        top_bar.transaction_label,
        top_bar.user_label,
        top_bar.role_label,
    ):
        assert isinstance(label, ElidedLabel)
        assert label.minimumSizeHint().width() == 0

    assert top_bar.version_label.text() == "Runtime: v2026.09.23-production"
    assert top_bar.sync_label.text() == "Sync: synchronizing-with-remote-runtime"


def test_desktop_window_policy_centers_a_first_run_window(app, tmp_path):
    settings = QSettings(str(tmp_path / "desktop.ini"), QSettings.Format.IniFormat)
    window = QMainWindow()
    window.setMinimumSize(640, 480)

    restored = apply_desktop_window_policy(window, settings=settings)

    assert restored is False
    assert window.width() >= 640
    assert window.height() >= 480


def test_desktop_window_policy_restores_saved_geometry(app, tmp_path):
    settings = QSettings(str(tmp_path / "desktop.ini"), QSettings.Format.IniFormat)
    first = QMainWindow()
    first.resize(900, 640)
    settings.setValue("ui/desktop/window_geometry", first.saveGeometry())
    settings.sync()

    restored_window = QMainWindow()
    restored_window.setMinimumSize(640, 480)
    restored = apply_desktop_window_policy(restored_window, settings=settings)

    assert restored is True


def test_workspace_header_uses_page_hierarchy_and_flexible_height(app):
    header = WorkspaceHeader("Student Workspace", "Students")
    source = Path(workspace_header_module.__file__).read_text(encoding="utf-8")

    assert header.page_title_label.text() == "Students"
    assert f"TYPOGRAPHY['page_title']" in source
    assert "setMinimumHeight" in source
    assert "setFixedHeight" not in source
    assert TYPOGRAPHY["page_title"] > TYPOGRAPHY["section_title"]


def test_desktop_polish_is_token_driven_and_shell_installed():
    desktop_source = Path(desktop_module.__file__).read_text(encoding="utf-8")
    shell_source = Path(application_shell_module.__file__).read_text(encoding="utf-8")

    assert "install_desktop_polish(self.window())" in shell_source
    assert "restoreGeometry" in desktop_source
    assert "saveGeometry" in desktop_source
    assert "QToolTip" in desktop_stylesheet()
    assert "QScrollBar" in desktop_stylesheet()
    assert "QMenu" in desktop_stylesheet()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", desktop_source)
