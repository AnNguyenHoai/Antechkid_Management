# -*- coding: utf-8 -*-
"""
Shared style constants for consistent UI across CenterManager.
"""
from PySide6.QtCore import Qt

# ===== Colors =====
COLORS = {
    "primary": "#1976d2",
    "primary_light": "#42a5f5",
    "primary_dark": "#1565c0",
    "success": "#4caf50",
    "warning": "#ff9800",
    "danger": "#d32f2f",
    "gray_100": "#f5f5f5",
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
FONT_FAMILY = "Segoe UI, Roboto, sans-serif"

# ===== Spacing =====
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

# ===== Border radius =====
BORDER_RADIUS = 8

# ===== Shadows =====
SHADOW_SM = """
    QFrame {
        border: none;
        background: white;
    }
"""
# Shadow will be applied via QGraphicsDropShadowEffect in code

# ===== Style sheets =====
CARD_STYLE = f"""
    QFrame {{
        background: white;
        border-radius: {BORDER_RADIUS}px;
        border: 1px solid {COLORS['gray_300']};
    }}
"""

CARD_STYLE_FLAT = f"""
    QFrame {{
        background: white;
        border-radius: {BORDER_RADIUS}px;
        border: none;
    }}
"""

SECTION_TITLE = f"""
    font-size: 18px;
    font-weight: 600;
    color: {COLORS['gray_900']};
"""

SECTION_SUBTITLE = f"""
    font-size: 13px;
    color: {COLORS['gray_600']};
    font-weight: 400;
"""

FIELD_LABEL = f"""
    font-size: 12px;
    color: {COLORS['gray_600']};
    font-weight: 500;
    letter-spacing: 0.3px;
    text-transform: uppercase;
"""

FIELD_VALUE = f"""
    font-size: 14px;
    color: {COLORS['gray_900']};
"""

EMPTY_STATE = f"""
    color: {COLORS['gray_500']};
    font-size: 14px;
"""

BUTTON_PRIMARY = f"""
    QPushButton {{
        background: {COLORS['primary']};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background: {COLORS['primary_dark']};
    }}
    QPushButton:pressed {{
        background: {COLORS['primary_dark']};
    }}
    QPushButton:disabled {{
        background: {COLORS['gray_400']};
        color: {COLORS['gray_600']};
    }}
"""

BUTTON_SECONDARY = f"""
    QPushButton {{
        background: transparent;
        color: {COLORS['gray_700']};
        border: 1px solid {COLORS['gray_400']};
        border-radius: 4px;
        padding: 6px 16px;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background: {COLORS['gray_200']};
        border-color: {COLORS['gray_500']};
    }}
    QPushButton:pressed {{
        background: {COLORS['gray_300']};
    }}
"""

BUTTON_DANGER = f"""
    QPushButton {{
        color: {COLORS['danger']};
        border: 1px solid {COLORS['danger']};
        border-radius: 4px;
        padding: 6px 16px;
        background: white;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background: #fde0e0;
    }}
    QPushButton:pressed {{
        background: #fcc;
    }}
"""

BUTTON_ICON = f"""
    QPushButton {{
        background: transparent;
        border: none;
        padding: 4px;
        font-size: 16px;
    }}
    QPushButton:hover {{
        background: {COLORS['gray_200']};
        border-radius: 4px;
    }}
"""

SEARCH_BAR = f"""
    QLineEdit {{
        background: white;
        border: 1px solid {COLORS['gray_300']};
        border-radius: 20px;
        padding: 6px 14px;
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border-color: {COLORS['primary']};
        outline: none;
    }}
"""

STAT_VALUE = f"""
    font-size: 28px;
    font-weight: 700;
    color: {COLORS['gray_900']};
"""

STAT_LABEL = f"""
    font-size: 13px;
    color: {COLORS['gray_600']};
    font-weight: 500;
    letter-spacing: 0.3px;
    text-transform: uppercase;
"""

STAT_ICON = f"""
    font-size: 24px;
"""

ACTIVITY_TITLE = f"""
    font-size: 14px;
    font-weight: 500;
    color: {COLORS['gray_900']};
"""

ACTIVITY_SUBTITLE = f"""
    font-size: 12px;
    color: {COLORS['gray_600']};
"""

ACTIVITY_TIME = f"""
    font-size: 11px;
    color: {COLORS['gray_400']};
"""

LIST_ITEM = f"""
    QWidget {{
        background: white;
        border: none;
        border-bottom: 1px solid {COLORS['gray_200']};
        padding: 8px 12px;
    }}
    QWidget:hover {{
        background: {COLORS['gray_100']};
    }}
    QWidget:selected {{
        background: {COLORS['primary_light']}22;
        border-left: 3px solid {COLORS['primary']};
    }}
"""