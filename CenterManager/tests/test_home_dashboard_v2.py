# -*- coding: utf-8 -*-
"""Regression coverage for UI-PROD-04 Home Dashboard V2."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QScrollArea

from centermanager.services.home_dashboard_service import WorkspaceSummary
from centermanager.ui.design_system.foundation import EmptyState, ErrorState
from centermanager.ui.home.home_page import HomePage
from centermanager.ui.home.workspace_card import WorkspaceCard


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


class FakeHomeService:
    def __init__(self, summaries=None, *, fail: bool = False):
        self.summaries = list(summaries or [])
        self.fail = fail
        self.refresh_calls = 0

    def get_workspace_summaries(self):
        if self.fail:
            raise RuntimeError("dashboard unavailable")
        return list(self.summaries)

    def refresh(self):
        self.refresh_calls += 1


def _summary(
    workspace_id: str,
    *,
    health_status: str = "good",
    health_details: str = "",
) -> WorkspaceSummary:
    return WorkspaceSummary(
        workspace_id=workspace_id,
        name=f"{workspace_id.title()} Workspace",
        icon="legacy-icon",
        description=f"Manage {workspace_id}",
        summary_text=f"{workspace_id.title()} operational summary",
        health_status=health_status,
        health_details=health_details,
        quick_action_label="Open",
        quick_action_target=workspace_id,
    )


def test_home_dashboard_renders_compact_operational_snapshot(app):
    service = FakeHomeService(
        [
            _summary("student"),
            _summary("class"),
            _summary("finance", health_status="warning", health_details="3 items to review"),
        ]
    )
    home = HomePage(service)

    assert isinstance(home.scroll_area, QScrollArea)
    assert home.scroll_area.widgetResizable()
    assert len(home._cards) == 3
    assert home.available_tile.value_label.text() == "3"
    assert home.healthy_tile.value_label.text() == "2"
    assert home.attention_tile.value_label.text() == "1"
    assert not home.attention_panel.isHidden()
    assert "Finance Workspace: 3 items to review" in home.attention_details.text()


def test_home_respects_service_filtered_workspace_list(app):
    service = FakeHomeService([_summary("student"), _summary("teacher")])
    home = HomePage(service)

    assert [card.workspace_id for card in home._cards] == ["student", "teacher"]
    assert all(isinstance(card, WorkspaceCard) for card in home._cards)


def test_workspace_action_preserves_navigation_signal_contract(app):
    service = FakeHomeService([_summary("student")])
    home = HomePage(service)
    received = []
    home.workspace_selected.connect(received.append)

    home._cards[0].action_btn.click()

    assert received == ["student"]


def test_manual_refresh_invalidates_service_cache(app):
    service = FakeHomeService([_summary("student")])
    home = HomePage(service)

    home.refresh(force=True)

    assert service.refresh_calls == 1
    assert len(home._cards) == 1


def test_empty_and_recoverable_error_states(app):
    empty_home = HomePage(FakeHomeService([]))
    assert isinstance(empty_home._state_widget, EmptyState)
    assert empty_home.dashboard_content.isHidden()

    service = FakeHomeService([_summary("student")], fail=True)
    failed_home = HomePage(service)
    assert isinstance(failed_home._state_widget, ErrorState)
    assert failed_home.dashboard_content.isHidden()

    service.fail = False
    failed_home.refresh(force=True)
    assert failed_home._state_widget is None
    assert not failed_home.dashboard_content.isHidden()
    assert len(failed_home._cards) == 1


def test_home_v2_sources_use_design_tokens_and_no_emoji_literals():
    paths = [
        Path("src/centermanager/ui/home/home_page.py"),
        Path("src/centermanager/ui/home/workspace_card.py"),
    ]
    emoji_pattern = re.compile(
        "["
        "\\U0001F300-\\U0001F5FF"
        "\\U0001F600-\\U0001F64F"
        "\\U0001F680-\\U0001F6FF"
        "\\U0001F900-\\U0001F9FF"
        "]"
    )
    raw_hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\\b")

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert raw_hex_pattern.search(source) is None, path
        assert emoji_pattern.search(source) is None, path
        assert "ui.styles" not in source, path


def test_home_ui_does_not_bypass_dashboard_service_permissions():
    source = Path("src/centermanager/ui/home/home_page.py").read_text(encoding="utf-8")

    assert "get_workspace_summaries" in source
    assert "has_permission(" not in source
    assert "get_current_user(" not in source
    assert "Repository" not in source
