# -*- coding: utf-8 -*-
"""Legacy style compatibility facade.

UI-PROD-01 removes this module as a visual-value owner. Existing callers can
continue importing the historical constants while all values now come from
``centermanager.ui.design_system.tokens``.

New code should import semantic tokens/theme from ``ui.design_system``.
"""
from centermanager.ui.design_system.tokens import COLORS, FONT_FAMILY, RADIUS, SPACING

BORDER_RADIUS = RADIUS["md"]

SHADOW_SM = f"""
    QFrame {{
        border: none;
        background: {COLORS['surface_card']};
    }}
"""

CARD_STYLE = f"""
    QFrame {{
        background: {COLORS['surface_card']};
        border-radius: {RADIUS['md']}px;
        border: 1px solid {COLORS['border_default']};
    }}
"""

CARD_STYLE_FLAT = f"""
    QFrame {{
        background: {COLORS['surface_card']};
        border-radius: {RADIUS['md']}px;
        border: none;
    }}
"""

SECTION_TITLE = f"""
    font-size: 18px;
    font-weight: 600;
    color: {COLORS['text_primary']};
"""

SECTION_SUBTITLE = f"""
    font-size: 13px;
    color: {COLORS['text_secondary']};
    font-weight: 400;
"""

FIELD_LABEL = f"""
    font-size: 12px;
    color: {COLORS['text_secondary']};
    font-weight: 500;
    letter-spacing: 0.3px;
    text-transform: uppercase;
"""

FIELD_VALUE = f"""
    font-size: 14px;
    color: {COLORS['text_primary']};
"""

EMPTY_STATE = f"""
    color: {COLORS['text_disabled']};
    font-size: 14px;
"""

BUTTON_PRIMARY = f"""
    QPushButton {{
        background: {COLORS['action_primary']};
        color: {COLORS['text_inverse']};
        border: none;
        border-radius: {RADIUS['sm']}px;
        padding: 6px 16px;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{ background: {COLORS['action_primary_hover']}; }}
    QPushButton:pressed {{ background: {COLORS['action_primary_hover']}; }}
    QPushButton:disabled {{
        background: {COLORS['gray_400']};
        color: {COLORS['text_secondary']};
    }}
"""

BUTTON_SECONDARY = f"""
    QPushButton {{
        background: transparent;
        color: {COLORS['text_secondary']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: {RADIUS['sm']}px;
        padding: 6px 16px;
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background: {COLORS['gray_200']};
        border-color: {COLORS['gray_500']};
    }}
    QPushButton:pressed {{ background: {COLORS['gray_300']}; }}
"""

BUTTON_DANGER = f"""
    QPushButton {{
        color: {COLORS['state_danger']};
        border: 1px solid {COLORS['state_danger']};
        border-radius: {RADIUS['sm']}px;
        padding: 6px 16px;
        background: {COLORS['surface_card']};
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{ background: {COLORS['state_danger_hover_bg']}; }}
    QPushButton:pressed {{ background: {COLORS['state_danger_pressed_bg']}; }}
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
        border-radius: {RADIUS['sm']}px;
    }}
"""

SEARCH_BAR = f"""
    QLineEdit {{
        background: {COLORS['surface_card']};
        border: 1px solid {COLORS['border_default']};
        border-radius: {RADIUS['pill']}px;
        padding: 6px 14px;
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border-color: {COLORS['action_primary']};
        outline: none;
    }}
"""

STAT_VALUE = f"font-size: 28px; font-weight: 700; color: {COLORS['text_primary']};"
STAT_LABEL = f"font-size: 13px; color: {COLORS['text_secondary']}; font-weight: 500; letter-spacing: 0.3px; text-transform: uppercase;"
STAT_ICON = "font-size: 24px;"
ACTIVITY_TITLE = f"font-size: 14px; font-weight: 500; color: {COLORS['text_primary']};"
ACTIVITY_SUBTITLE = f"font-size: 12px; color: {COLORS['text_secondary']};"
ACTIVITY_TIME = f"font-size: 11px; color: {COLORS['gray_400']};"

LIST_ITEM = f"""
    QWidget {{
        background: {COLORS['surface_card']};
        border: none;
        border-bottom: 1px solid {COLORS['gray_200']};
        padding: 8px 12px;
    }}
    QWidget:hover {{ background: {COLORS['gray_100']}; }}
    QWidget:selected {{
        background: {COLORS['blue_50']};
        border-left: 3px solid {COLORS['action_primary']};
    }}
"""
