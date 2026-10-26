# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2F header information architecture."""
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from centermanager.ui.application_shell import ApplicationTopBar


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_header_uses_three_zone_information_architecture():
    source = _source("application_shell.py")

    assert 'brand_zone.setObjectName("HeaderBrandZone")' in source
    assert 'self.guidance_panel = _EditingGuidancePanel(self.header)' in source
    assert 'control_zone.setObjectName("HeaderControlZone")' in source
    assert "header_layout.addWidget(brand_zone, 32)" in source
    assert "header_layout.addWidget(self.guidance_panel, 36)" in source
    assert "header_layout.addWidget(control_zone, 32)" in source


def test_header_statuses_use_vector_icon_pills_without_emoji_dependency():
    shell = _source("application_shell.py")
    icons = _source("app_icon.py")

    assert "class _HeaderPill(QFrame):" in shell
    assert 'icon="edit"' in shell
    assert 'icon="users"' in shell
    assert 'icon="check"' in shell
    assert '"edit":' in icons
    assert '"users":' in icons
    assert '"info":' in icons
    assert '"arrow_right":' in icons


def test_guidance_follows_existing_mode_and_transaction_projections(app):
    top = ApplicationTopBar(user_name="An", runtime_version="v1", sync_status="idle")

    assert "Start editing" in top.guidance_panel.label.text()

    top.set_mode("WRITE", "success")
    top.set_transaction_text("Editing")
    assert "Finish editing" in top.guidance_panel.label.text()

    top.set_transaction_text("Waiting (pos 2) - Other user")
    assert "Another edit session" in top.guidance_panel.label.text()

    top.set_mode("CONFLICT", "danger")
    top.set_transaction_text("Data changed on another computer")
    assert "Resolve or refresh" in top.guidance_panel.label.text()


def test_legacy_editor_text_is_sanitized_before_rendering(app):
    top = ApplicationTopBar(user_name="An")
    top.waiting_indicator.setText("✏️ You are editing")
    assert top.waiting_indicator.text() == "You are editing"
    top.waiting_indicator.setText("🔒 Other user is editing")
    assert top.waiting_indicator.text() == "Other user is editing"


def test_primary_edit_actions_keep_finish_action_visually_prominent(app):
    top = ApplicationTopBar(user_name="An")
    source = _source("application_shell.py")

    assert top.start_edit_button.objectName() == "HeroPrimaryEditAction"
    assert top.finish_edit_button.objectName() == "HeroPrimaryEditAction"
    assert top.start_edit_button.height() == 48
    assert top.finish_edit_button.height() == 48
    assert 'Button("Start editing", variant="primary", size="lg")' in source
    assert 'Button("Finish editing", variant="accent", size="lg")' in source


def test_header_responsive_contract_hides_secondary_content_first():
    source = _source("application_shell.py")
    tokens = _source("design_system/tokens.py")

    assert "def resizeEvent(self, event)" in source
    assert "self.product_label.setVisible(not compact)" in source
    assert "self.guidance_panel.setVisible(not narrow)" in source
    assert '"hero_header_compact_breakpoint": 1180' in tokens
    assert '"hero_header_guidance_breakpoint": 1040' in tokens


def test_header_keeps_nested_effect_regression_fix():
    source = _source("application_shell.py")

    assert "QGraphicsOpacityEffect" not in source
    assert "self.state_zone.setGraphicsEffect" not in source
    assert 'self._header_shadow, b"blurRadius", self' in source
