# -*- coding: utf-8 -*-
"""Regression contracts for UI Phase 2A shared visual components."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "src" / "centermanager" / "ui" / "shared"


def _source(name: str) -> str:
    return (SHARED / name).read_text(encoding="utf-8")


def test_metric_card_uses_token_driven_icon_tile_and_compact_density():
    source = _source("metric_card.py")

    assert 'self.setObjectName("SharedMetricCard")' in source
    assert 'tone: str = "neutral"' in source
    assert 'compact: bool = False' in source
    assert '"primary": (COLORS["blue_50"], COLORS["action_primary"])' in source
    assert 'icon_label.setObjectName("MetricIconTile")' in source
    assert 'self.setMinimumHeight(84 if self._compact else 96)' in source
    assert 'font-size: {TYPOGRAPHY[\'stat_value\']}px' in source


def test_statistic_grid_balances_columns_and_passes_visual_metadata():
    source = _source("statistic_grid.py")

    assert "columns: Optional[int] = None" in source
    assert "min(len(metrics), 4)" in source
    assert "self._layout.setColumnStretch(column, 1)" in source
    assert 'tone=metric.get("tone", "neutral")' in source
    assert 'compact=bool(metric.get("compact", False))' in source


def test_section_header_uses_shared_typography_and_optional_action():
    source = _source("section_header.py")

    assert 'self.title_label.setObjectName("SharedSectionTitle")' in source
    assert 'self.subtitle_label.setObjectName("SharedSectionSubtitle")' in source
    assert 'self.action_button.setObjectName("SharedSectionAction")' in source
    assert "FONT_WEIGHTS['semibold']" in source
    assert "COLORS['text_muted']" in source


def test_warning_banner_has_actionable_keyboard_accessible_visual_state():
    source = _source("warning_banner.py")

    assert 'self.setObjectName("SharedWarningBanner")' in source
    assert "self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)" in source
    assert 'icon_label.setObjectName("WarningIconTile")' in source
    assert "Qt.Key.Key_Return" in source
    assert "Qt.Key.Key_Space" in source
    assert 'COLORS["state_warning_bg"]' in source
    assert 'COLORS["state_danger_bg"]' in source


def test_activity_card_uses_consistent_icon_title_subtitle_time_hierarchy():
    source = _source("activity_card.py")

    assert 'self.setObjectName("SharedActivityCard")' in source
    assert 'icon_label.setObjectName("ActivityIconTile")' in source
    assert 'title_label.setObjectName("ActivityTitle")' in source
    assert 'sub_label.setObjectName("ActivitySubtitle")' in source
    assert 'time_label.setObjectName("ActivityTime")' in source
    assert 'return f"Yesterday {dt.strftime(\'%H:%M\')}"' in source


def test_data_table_has_explicit_focus_and_selected_row_states():
    source = _source("data_table.py")

    assert 'QTableWidget#DataTableGrid:focus' in source
    assert 'border: 2px solid {COLORS["focus_ring"]};' in source
    assert 'QTableWidget#DataTableGrid::item:selected' in source
    assert 'background-color: {COLORS["action_primary_selected"]};' in source
