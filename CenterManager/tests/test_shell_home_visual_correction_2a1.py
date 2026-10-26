# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2A.1 shell/home visual correction."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "src" / "centermanager" / "ui"


def _source(relative: str) -> str:
    return (UI / relative).read_text(encoding="utf-8")


def test_vector_icon_system_does_not_depend_on_emoji_font_fallback():
    source = _source("app_icon.py")

    assert "from PySide6.QtSvg import QSvgRenderer" in source
    assert 'class AppIcon(QLabel)' in source
    assert '"home":' in source
    assert '"student":' in source
    assert '"teacher":' in source
    assert '"class":' in source
    assert '"finance":' in source
    assert '"employee":' in source
    assert '"settings":' in source
    assert '"reports":' in source
    assert "def set_color" in source


def test_global_sidebar_uses_vector_icons_and_stable_alignment():
    source = _source("global_navigation.py")

    assert "from centermanager.ui.app_icon import AppIcon" in source
    assert "self.setFixedWidth(204)" in source
    assert 'self._add_item(root, "student", "student", "Student Workspace")' in source
    assert 'self._add_item(root, "finance", "finance", "Finance Workspace")' in source
    assert 'self.icon_widget = AppIcon(' in source
    assert 'self.label_widget = QLabel(label, self)' in source
    assert 'super().__init__(f"{icon}  {label}", parent)' not in source


def test_top_bar_branding_is_owned_by_hero_header():
    source = _source("application_shell.py")

    assert 'self.header.setObjectName("ApplicationHeroHeader")' in source
    assert 'brand_label = QLabel("ANTECHKIDS", brand_zone)' in source
    assert 'self.product_label = QLabel(APPLICATION_PRODUCT_NAME, brand_zone)' in source
    assert 'self.version_label = _HeaderPill(' in source
    assert 'self.sync_label = _HeaderPill(' in source


def test_home_workspace_cards_have_one_density_and_one_cta():
    source = _source("home/workspace_card.py")

    assert "self.setMinimumHeight(146)" in source
    assert "self.setMaximumHeight(164)" in source
    assert 'self.description_label.setVisible(False)' in source
    assert 'self.action_btn = Button("Open →"' in source
    assert 'self.icon_label = AppIcon(' in source
    assert 'min_height = 230' not in source


def test_home_grid_uses_equal_columns_without_featured_row_spans():
    source = _source("home/home_page.py")

    assert "for column in range(3):" in source
    assert "self.workspace_grid.setColumnStretch(column, 1)" in source
    assert '"student": (0, 0, 2, 1, "featured")' not in source
    assert "row = index // 3" in source
    assert "column = index % 3" in source
    assert "self.workspace_grid.addWidget(card, row, column)" in source


def test_home_internal_labels_explicitly_stay_transparent():
    source = _source("home/home_page.py")

    assert "QLabel#HomePanelEyebrow" in source
    assert "QLabel#HomeInfoTitle" in source
    assert "QLabel#HomeInfoDetail" in source
    assert source.count("background: transparent;") >= 5
