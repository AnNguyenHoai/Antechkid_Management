# -*- coding: utf-8 -*-
"""
Design Tokens - Colors, Typography, Spacing, etc.
"""
# ===== Colors =====
COLORS = {
    # Primary
    "primary": "#1976d2",
    "primary_light": "#42a5f5",
    "primary_dark": "#1565c0",
    "primary_hover": "#e3f2fd",
    "primary_selected": "#bbdefb",
    
    # Status
    "success": "#2e7d32",
    "success_bg": "#e8f5e9",
    "warning": "#ed6c02",
    "warning_bg": "#fff3e0",
    "danger": "#d32f2f",
    "danger_bg": "#ffebee",
    "info": "#0288d1",
    "info_bg": "#e1f5fe",
    
    # Grays
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
    
    # Surfaces
    "background": "#f5f7fa",
    "surface": "#ffffff",
    "surface_hover": "#f8f9fa",
    "surface_pressed": "#f0f0f0",
    "border": "#e0e0e0",
    "border_light": "#f0f0f0",
    
    # Text
    "text_primary": "#1a1a1a",
    "text_secondary": "#424242",
    "text_muted": "#9e9e9e",
    "text_white": "#ffffff",
    
    # === ALIASES for backward compatibility (keep old keys) ===
    "muted": "#9e9e9e",           # alias for text_muted
    "muted_light": "#bdbdbd",      # alias for gray_400
    "gray_100": "#f5f5f5",         # already defined, but keep explicit
    "gray_200": "#eeeeee",
    "gray_300": "#e0e0e0",
    "gray_400": "#bdbdbd",
    "gray_500": "#9e9e9e",
    "gray_600": "#757575",
    "gray_700": "#616161",
    "gray_800": "#424242",
    "gray_900": "#212121",
}

# ===== Typography =====
TYPOGRAPHY = {
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

# ===== Spacing =====
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
    "xxxl": 48,
}

# ===== Border Radius =====
BORDER_RADIUS = {
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "circle": 999,
}

# ===== Shadows =====
SHADOWS = {
    "sm": "0 1px 3px rgba(0,0,0,0.08)",
    "md": "0 2px 8px rgba(0,0,0,0.10)",
    "lg": "0 4px 16px rgba(0,0,0,0.12)",
}

# ===== Badge Colors =====
BADGE_COLORS = {
    "ACTIVE": {"bg": "#e8f5e9", "text": "#2e7d32"},
    "INACTIVE": {"bg": "#ffebee", "text": "#c62828"},
    "ARCHIVED": {"bg": "#f5f5f5", "text": "#616161"},
    "SCHEDULED": {"bg": "#e3f2fd", "text": "#0d47a1"},
    "COMPLETED": {"bg": "#e8f5e9", "text": "#2e7d32"},
    "CANCELLED": {"bg": "#ffebee", "text": "#c62828"},
    "POSTPONED": {"bg": "#fff3e0", "text": "#e65100"},
    "EXCELLENT": {"bg": "#e8f5e9", "text": "#2e7d32"},
    "GOOD": {"bg": "#e3f2fd", "text": "#0d47a1"},
    "NORMAL": {"bg": "#fff3e0", "text": "#e65100"},
    "NEED_IMPROVEMENT": {"bg": "#ffebee", "text": "#c62828"},
    "WARNING": {"bg": "#fff3e0", "text": "#e65100"},
}