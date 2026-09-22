# -*- coding: utf-8 -*-
"""UI-PROD-01 Design System V2 contract tests."""
from __future__ import annotations

import re
from pathlib import Path

from centermanager.ui.design_system.tokens import (
    BADGE_COLORS,
    BORDER_RADIUS,
    COLORS,
    ELEVATION,
    FONT_FAMILY,
    RADIUS,
    SPACING,
    STATES,
    TOKEN_SCHEMA_VERSION,
    TYPOGRAPHY,
)
from centermanager.ui.design_system.theme import DEFAULT_THEME
from centermanager.ui import styles as legacy_styles


def test_semantic_token_contract_is_complete() -> None:
    assert TOKEN_SCHEMA_VERSION == 2

    for name in (
        "surface_app",
        "surface_page",
        "surface_card",
        "text_primary",
        "text_secondary",
        "text_muted",
        "border_default",
        "border_subtle",
        "action_primary",
        "action_primary_hover",
        "action_accent",
        "state_success",
        "state_warning",
        "state_danger",
        "state_info",
    ):
        assert name in COLORS

    assert {"page_title", "section_title", "body", "caption"} <= TYPOGRAPHY.keys()
    assert {"xs", "sm", "md", "lg", "xl", "xxl"} <= SPACING.keys()
    assert {"sm", "md", "lg", "xl", "pill"} <= RADIUS.keys()
    assert {"none", "sm", "md", "lg"} <= ELEVATION.keys()
    assert {
        "default", "hover", "pressed", "selected", "disabled",
        "success", "warning", "danger", "info",
    } <= STATES.keys()


def test_theme_facade_references_canonical_tokens() -> None:
    assert DEFAULT_THEME.colors is COLORS
    assert DEFAULT_THEME.typography is TYPOGRAPHY
    assert DEFAULT_THEME.spacing is SPACING
    assert DEFAULT_THEME.radius is RADIUS
    assert DEFAULT_THEME.elevation is ELEVATION
    assert DEFAULT_THEME.states is STATES
    assert DEFAULT_THEME.font_family == FONT_FAMILY


def test_legacy_style_module_no_longer_owns_visual_values() -> None:
    assert legacy_styles.COLORS is COLORS
    assert legacy_styles.SPACING is SPACING
    assert legacy_styles.BORDER_RADIUS == RADIUS["md"]

    source = Path(legacy_styles.__file__).read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)


def test_legacy_token_aliases_resolve_to_v2_semantics() -> None:
    assert COLORS["primary"] == COLORS["action_primary"]
    assert COLORS["primary_dark"] == COLORS["action_primary_hover"]
    assert COLORS["success"] == COLORS["state_success"]
    assert COLORS["warning"] == COLORS["state_warning"]
    assert COLORS["danger"] == COLORS["state_danger"]
    assert COLORS["background"] == COLORS["surface_app"]
    assert COLORS["surface"] == COLORS["surface_card"]
    assert COLORS["border"] == COLORS["border_default"]
    assert BORDER_RADIUS is RADIUS


def test_badge_colors_are_derived_from_canonical_palette() -> None:
    palette_values = set(COLORS.values())
    assert BADGE_COLORS
    for badge in BADGE_COLORS.values():
        assert badge["bg"] in palette_values
        assert badge["text"] in palette_values
