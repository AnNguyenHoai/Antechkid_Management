# -*- coding: utf-8 -*-
"""CenterManager Design System V2 tokens.

This module is the single source of truth for visual constants. Product UI
code may consume semantic tokens from here (preferably through ``theme.py``)
but must not define competing palettes or spacing/type scales.

UI-PROD-01 keeps legacy token names as aliases so existing screens can migrate
incrementally. UI-PROD-02 adds component geometry; UI-PROD-03 adds shell metrics.
"""
from __future__ import annotations

TOKEN_SCHEMA_VERSION = 2

# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------
COLORS = {
    "brand_blue_300": "#42a5f5",
    "brand_blue_500": "#1976d2",
    "brand_blue_700": "#1565c0",
    "brand_blue_900": "#0d47a1",
    "brand_orange_500": "#f57c00",
    "brand_orange_700": "#e65100",
    "gray_50": "#fafafa",
    "gray_100": "#f5f5f5",
    "gray_200": "#eeeeee",
    "gray_300": "#e0e0e0",
    "gray_400": "#bdbdbd",
    "gray_500": "#9e9e9e",
    "gray_600": "#757575",
    "gray_700": "#616161",
    "gray_800": "#424242",
    "gray_900": "#212121",
    "green_50": "#e8f5e9",
    "green_800": "#2e7d32",
    "amber_50": "#fff3e0",
    "amber_800": "#ed6c02",
    "red_50": "#ffebee",
    "red_100": "#fde0e0",
    "red_200": "#ffcccc",
    "red_700": "#d32f2f",
    "red_800": "#c62828",
    "cyan_50": "#e1f5fe",
    "cyan_700": "#0288d1",
    "blue_50": "#e3f2fd",
    "blue_100": "#bbdefb",
    "surface_app": "#f5f7fa",
    "surface_page": "#ffffff",
    "surface_card": "#ffffff",
    "surface_hover": "#f8f9fa",
    "surface_pressed": "#f0f0f0",
    "surface_disabled": "#f5f5f5",
    "text_primary": "#1a1a1a",
    "text_secondary": "#424242",
    "text_muted": "#9e9e9e",
    "text_disabled": "#9e9e9e",
    "text_inverse": "#ffffff",
    "border_default": "#e0e0e0",
    "border_subtle": "#f0f0f0",
    "border_strong": "#bdbdbd",
    "focus_ring": "#42a5f5",
    "action_primary": "#1976d2",
    "action_primary_hover": "#1565c0",
    "action_primary_selected": "#bbdefb",
    "action_accent": "#f57c00",
    "action_accent_hover": "#e65100",
    "state_success": "#2e7d32",
    "state_success_bg": "#e8f5e9",
    "state_warning": "#ed6c02",
    "state_warning_bg": "#fff3e0",
    "state_danger": "#d32f2f",
    "state_danger_bg": "#ffebee",
    "state_danger_hover_bg": "#fde0e0",
    "state_danger_pressed_bg": "#ffcccc",
    "state_info": "#0288d1",
    "state_info_bg": "#e1f5fe",
    "shadow_color": "#000000",
}

COLORS.update({
    "primary": COLORS["action_primary"],
    "primary_light": COLORS["brand_blue_300"],
    "primary_dark": COLORS["action_primary_hover"],
    "primary_hover": COLORS["blue_50"],
    "primary_selected": COLORS["action_primary_selected"],
    "success": COLORS["state_success"],
    "success_bg": COLORS["state_success_bg"],
    "warning": COLORS["state_warning"],
    "warning_bg": COLORS["state_warning_bg"],
    "danger": COLORS["state_danger"],
    "danger_bg": COLORS["state_danger_bg"],
    "info": COLORS["state_info"],
    "info_bg": COLORS["state_info_bg"],
    "background": COLORS["surface_app"],
    "surface": COLORS["surface_card"],
    "border": COLORS["border_default"],
    "border_light": COLORS["border_subtle"],
    "muted": COLORS["text_disabled"],
    "muted_light": COLORS["gray_400"],
    "text_white": COLORS["text_inverse"],
})

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_FAMILY = "Segoe UI, Roboto, Arial, sans-serif"
FONT_WEIGHTS = {
    "regular": 400,
    "medium": 500,
    "semibold": 600,
    "bold": 700,
}
TYPOGRAPHY = {
    "display": 32,
    "page_title": 26,
    "section_title": 18,
    "card_title": 16,
    "body_large": 15,
    "body": 14,
    "body_small": 13,
    "caption": 12,
    "badge": 11,
    "stat_value": 24,
    "stat_value_large": 32,
    "icon": 18,
    "icon_large": 40,
    "icon_small": 16,
}

# ---------------------------------------------------------------------------
# Spacing
# ---------------------------------------------------------------------------
SPACING = {
    "none": 0,
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
    "xxxl": 48,
}

# ---------------------------------------------------------------------------
# Radius
# ---------------------------------------------------------------------------
RADIUS = {
    "none": 0,
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "pill": 999,
    "circle": 999,
}
BORDER_RADIUS = RADIUS

# ---------------------------------------------------------------------------
# Elevation
# ---------------------------------------------------------------------------
ELEVATION = {
    "none": {"blur_radius": 0, "x_offset": 0, "y_offset": 0, "alpha": 0},
    "sm": {"blur_radius": 8, "x_offset": 0, "y_offset": 1, "alpha": 20},
    "md": {"blur_radius": 16, "x_offset": 0, "y_offset": 3, "alpha": 28},
    "lg": {"blur_radius": 28, "x_offset": 0, "y_offset": 6, "alpha": 36},
}
SHADOWS = {
    "sm": "0 1px 3px rgba(0,0,0,0.08)",
    "md": "0 2px 8px rgba(0,0,0,0.10)",
    "lg": "0 4px 16px rgba(0,0,0,0.12)",
}

# ---------------------------------------------------------------------------
# Interaction / status state
# ---------------------------------------------------------------------------
STATES = {
    "default": {"background": COLORS["surface_card"], "foreground": COLORS["text_primary"], "border": COLORS["border_default"]},
    "hover": {"background": COLORS["surface_hover"], "foreground": COLORS["text_primary"], "border": COLORS["border_strong"]},
    "pressed": {"background": COLORS["surface_pressed"], "foreground": COLORS["text_primary"], "border": COLORS["border_strong"]},
    "selected": {"background": COLORS["action_primary_selected"], "foreground": COLORS["action_primary_hover"], "border": COLORS["action_primary"]},
    "disabled": {"background": COLORS["surface_disabled"], "foreground": COLORS["text_disabled"], "border": COLORS["border_default"]},
    "success": {"background": COLORS["state_success_bg"], "foreground": COLORS["state_success"], "border": COLORS["state_success"]},
    "warning": {"background": COLORS["state_warning_bg"], "foreground": COLORS["state_warning"], "border": COLORS["state_warning"]},
    "danger": {"background": COLORS["state_danger_bg"], "foreground": COLORS["state_danger"], "border": COLORS["state_danger"]},
    "info": {"background": COLORS["state_info_bg"], "foreground": COLORS["state_info"], "border": COLORS["state_info"]},
}

# ---------------------------------------------------------------------------
# Component scale
# ---------------------------------------------------------------------------
CONTROL_SIZES = {
    "sm": {"height": 30, "padding_x": SPACING["sm"], "font_size": TYPOGRAPHY["body_small"]},
    "md": {"height": 36, "padding_x": SPACING["md"], "font_size": TYPOGRAPHY["body"]},
    "lg": {"height": 44, "padding_x": SPACING["lg"], "font_size": TYPOGRAPHY["body_large"]},
}

COMPONENT_METRICS = {
    "border_width": 1,
    "badge_height": 22,
    "toolbar_height": 48,
    "tab_height": 38,
    "tab_min_width": 80,
    "tab_indicator_width": 2,
    "dialog_min_width": 480,
    "state_max_width": 520,
    "state_symbol_size": 40,
    "loading_width": 160,
    "loading_height": 8,
    "skeleton_row_height": 48,
    # Application Shell V2
    "app_top_bar_height": 60,
    "workspace_sidebar_width": 224,
    "workspace_sidebar_header_height": 72,
    "page_header_height": 78,
    "nav_indicator_width": 3,
}

BADGE_COLORS = {
    "ACTIVE": {"bg": STATES["success"]["background"], "text": STATES["success"]["foreground"]},
    "INACTIVE": {"bg": STATES["danger"]["background"], "text": COLORS["red_800"]},
    "ARCHIVED": {"bg": COLORS["gray_100"], "text": COLORS["gray_700"]},
    "SCHEDULED": {"bg": COLORS["blue_50"], "text": COLORS["brand_blue_900"]},
    "COMPLETED": {"bg": STATES["success"]["background"], "text": STATES["success"]["foreground"]},
    "CANCELLED": {"bg": STATES["danger"]["background"], "text": COLORS["red_800"]},
    "POSTPONED": {"bg": STATES["warning"]["background"], "text": COLORS["brand_orange_700"]},
    "EXCELLENT": {"bg": STATES["success"]["background"], "text": STATES["success"]["foreground"]},
    "GOOD": {"bg": COLORS["blue_50"], "text": COLORS["brand_blue_900"]},
    "NORMAL": {"bg": STATES["warning"]["background"], "text": COLORS["brand_orange_700"]},
    "NEED_IMPROVEMENT": {"bg": STATES["danger"]["background"], "text": COLORS["red_800"]},
    "WARNING": {"bg": STATES["warning"]["background"], "text": COLORS["brand_orange_700"]},
}

__all__ = [
    "TOKEN_SCHEMA_VERSION",
    "COLORS",
    "FONT_FAMILY",
    "FONT_WEIGHTS",
    "TYPOGRAPHY",
    "SPACING",
    "RADIUS",
    "BORDER_RADIUS",
    "ELEVATION",
    "SHADOWS",
    "STATES",
    "CONTROL_SIZES",
    "COMPONENT_METRICS",
    "BADGE_COLORS",
]
