# -*- coding: utf-8 -*-
"""Semantic theme facade for CenterManager Design System V2.

``tokens.py`` owns every visual value. This module gives consumers one
discoverable object without creating a second source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .tokens import (
    BADGE_COLORS,
    COLORS,
    ELEVATION,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    STATES,
    TYPOGRAPHY,
)


@dataclass(frozen=True)
class DesignTheme:
    """Read-oriented facade over the canonical token dictionaries."""

    colors: Mapping[str, str]
    typography: Mapping[str, int]
    font_weights: Mapping[str, int]
    spacing: Mapping[str, int]
    radius: Mapping[str, int]
    elevation: Mapping[str, Mapping[str, int]]
    states: Mapping[str, Mapping[str, str]]
    badge_colors: Mapping[str, Mapping[str, str]]
    font_family: str

    def color(self, name: str) -> str:
        return self.colors[name]

    def space(self, name: str) -> int:
        return self.spacing[name]

    def radius_px(self, name: str = "md") -> int:
        return self.radius[name]

    def type_px(self, name: str = "body") -> int:
        return self.typography[name]

    def elevation_spec(self, name: str = "none") -> Mapping[str, int]:
        return self.elevation[name]

    def state(self, name: str = "default") -> Mapping[str, str]:
        return self.states[name]


DEFAULT_THEME = DesignTheme(
    colors=COLORS,
    typography=TYPOGRAPHY,
    font_weights=FONT_WEIGHTS,
    spacing=SPACING,
    radius=RADIUS,
    elevation=ELEVATION,
    states=STATES,
    badge_colors=BADGE_COLORS,
    font_family=FONT_FAMILY,
)

theme = DEFAULT_THEME

__all__ = ["DesignTheme", "DEFAULT_THEME", "theme"]
