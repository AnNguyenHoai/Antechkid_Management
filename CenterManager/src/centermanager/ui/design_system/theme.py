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
    COMPONENT_METRICS,
    CONTROL_SIZES,
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
    control_sizes: Mapping[str, Mapping[str, int]]
    component_metrics: Mapping[str, int]
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

    def control(self, name: str = "md") -> Mapping[str, int]:
        return self.control_sizes[name]

    def metric(self, name: str) -> int:
        return self.component_metrics[name]


DEFAULT_THEME = DesignTheme(
    colors=COLORS,
    typography=TYPOGRAPHY,
    font_weights=FONT_WEIGHTS,
    spacing=SPACING,
    radius=RADIUS,
    elevation=ELEVATION,
    states=STATES,
    control_sizes=CONTROL_SIZES,
    component_metrics=COMPONENT_METRICS,
    badge_colors=BADGE_COLORS,
    font_family=FONT_FAMILY,
)

theme = DEFAULT_THEME

__all__ = ["DesignTheme", "DEFAULT_THEME", "theme"]
