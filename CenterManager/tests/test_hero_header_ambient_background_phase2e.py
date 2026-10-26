# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2E hero header and ambient background."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_hero_header_exposes_reference_visual_hierarchy_without_changing_edit_api():
    source = _source("application_shell.py")

    assert 'self.header.setObjectName("ApplicationHeroHeader")' in source
    assert 'brand_label = QLabel("ANTECHKIDS", brand_zone)' in source
    assert 'product_label = QLabel(APPLICATION_PRODUCT_NAME, brand_zone)' in source
    assert 'self.version_label = ElidedLabel(' in source
    assert 'self.sync_label = ElidedLabel(' in source
    assert 'self.mode_badge = Badge("Mode: READ"' in source
    assert 'self.editor_badge = Badge("No active editor"' in source
    assert 'self.transaction_label = ElidedLabel("Ready")' in source
    assert 'self.start_edit_button = Button("Start editing", variant="primary", size="lg")' in source
    assert 'self.finish_edit_button = Button("Finish editing", variant="accent", size="lg")' in source
    assert 'self.user_avatar = QLabel(initials, right_zone)' in source
    assert 'accent.setObjectName("HeroAccentLine")' in source


def test_hero_header_uses_deterministic_vector_status_icons():
    shell = _source("application_shell.py")
    icons = _source("app_icon.py")

    assert 'AppIcon("key"' in shell
    assert 'AppIcon("student"' in shell
    assert 'AppIcon("check"' in shell
    assert '"key":' in icons


def test_ambient_background_is_responsive_painted_surface_not_raster_wallpaper():
    source = _source("shared/ambient_background.py")

    assert "class AmbientBackground(QWidget):" in source
    assert "def paintEvent" in source
    assert "QLinearGradient" in source
    assert "def _paint_network" in source
    assert "def _paint_blocks" in source
    assert "def _paint_chip" in source
    assert "def _paint_gears" in source
    assert "QPixmap" not in source


def test_application_shell_hosts_ambient_background_and_keeps_workspace_stack():
    source = _source("main_window.py")

    assert "from centermanager.ui.shared import AmbientBackground" in source
    assert "root = AmbientBackground(self)" in source
    assert 'shell_body.setStyleSheet("QWidget#ApplicationShellBody { background: transparent; }")' in source
    assert "self.central_stack = QStackedWidget(shell_body)" in source
    assert "self.global_sidebar = GlobalSidebar(shell_body)" in source


def test_home_reveals_ambient_surface_without_making_cards_translucent():
    home = _source("home/home_page.py")
    cards = _source("home/workspace_card.py")

    assert 'self.setStyleSheet("QWidget#HomeDashboardV3 { background: transparent; }")' in home
    assert "self.scroll_area.viewport().setAutoFillBackground(False)" in home
    assert 'self.container.setStyleSheet("QWidget#HomeDashboardContent { background: transparent; }")' in home
    assert "background-color: {COLORS['surface_card']}" in cards or 'background: {COLORS["surface_card"]}' in cards


def test_phase_2e_geometry_is_token_owned():
    tokens = _source("design_system/tokens.py")

    assert '"app_top_bar_height": 136' in tokens
    assert '"hero_header_card_height": 116' in tokens
    assert '"hero_header_accent_height": 5' in tokens
    assert '"ambient_base_start":' in tokens
    assert '"ambient_network":' in tokens
