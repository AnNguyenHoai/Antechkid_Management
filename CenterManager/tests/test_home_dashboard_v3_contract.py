# -*- coding: utf-8 -*-
"""Source-level guardrails for PR-D Home Dashboard V3.

These tests intentionally protect the presentation-only boundary without requiring
Qt rendering in headless CI.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME_PAGE = ROOT / "src" / "centermanager" / "ui" / "home" / "home_page.py"
WORKSPACE_CARD = ROOT / "src" / "centermanager" / "ui" / "home" / "workspace_card.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_home_v3_has_required_information_hierarchy() -> None:
    source = _source(HOME_PAGE)
    assert 'self.setObjectName("HomeDashboardV3")' in source
    assert 'QLabel("TODAY"' in source
    assert '"ATTENTION"' in source
    assert '"QUICK ACCESS"' in source
    assert 'QLabel("Workspace launcher"' in source


def test_home_v3_keeps_service_and_navigation_contract() -> None:
    source = _source(HOME_PAGE)
    assert "HomeDashboardService" in source
    assert "get_workspace_summaries()" in source
    assert "workspace_selected = Signal(str)" in source
    assert "self.workspace_selected.emit(workspace_id)" in source
    assert "card.clicked.connect(self._on_workspace_clicked)" in source


def test_home_v3_metrics_are_derived_from_workspace_summaries() -> None:
    source = _source(HOME_PAGE)
    assert "len(summaries)" in source
    assert 'item.health_status in {"warning", "critical"}' in source
    assert "health_details" in source
    # PR-D is presentation-only: no repository/database access belongs here.
    assert "sqlite3" not in source
    assert "Repository(" not in source
    assert "Session(" not in source


def test_workspace_card_preserves_single_workspace_selection_contract() -> None:
    source = _source(WORKSPACE_CARD)
    assert "clicked = Signal(str)" in source
    assert "self.clicked.emit(self._workspace_id)" in source
    assert "quick_action_label" in source
