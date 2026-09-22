# -*- coding: utf-8 -*-
"""UI-PROD-02 component foundation contract tests."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from centermanager.ui import design_system as ds
from centermanager.ui.design_system import foundation
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    CONTROL_SIZES,
)
from centermanager.ui.shared.empty_state import EmptyState as SharedEmptyState
from centermanager.ui.shared.error_state import ErrorState as SharedErrorState
from centermanager.ui.shared.loading_widget import LoadingSkeleton, LoadingWidget


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    yield instance


@pytest.mark.parametrize(
    "name",
    [
        "Button",
        "Input",
        "Select",
        "Badge",
        "Card",
        "Toolbar",
        "Tabs",
        "Dialog",
        "EmptyState",
        "LoadingState",
        "ErrorState",
    ],
)
def test_foundation_components_are_public(name):
    assert getattr(ds, name) is getattr(foundation, name)


def test_component_geometry_is_token_owned():
    assert set(CONTROL_SIZES) == {"sm", "md", "lg"}
    assert CONTROL_SIZES["sm"]["height"] < CONTROL_SIZES["md"]["height"]
    assert CONTROL_SIZES["md"]["height"] < CONTROL_SIZES["lg"]["height"]

    required = {
        "border_width",
        "badge_height",
        "toolbar_height",
        "tab_height",
        "dialog_min_width",
        "state_max_width",
    }
    assert required.issubset(COMPONENT_METRICS)


def test_foundation_source_has_no_raw_hex_colors():
    source = Path(foundation.__file__).read_text(encoding="utf-8")
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b", source) == []


def test_button_variants_and_sizes(app):
    button = ds.Button("Save", variant=ds.ButtonVariant.PRIMARY)
    assert button.variant == "primary"
    assert button.height() == CONTROL_SIZES["md"]["height"]

    button.set_variant(ds.ButtonVariant.DANGER)
    button.set_size(ds.ComponentSize.LARGE)
    assert button.variant == "danger"
    assert button.height() == CONTROL_SIZES["lg"]["height"]
    assert COLORS["state_danger"] in button.styleSheet()


def test_input_and_select_validation_states(app):
    text_input = ds.Input("Student name", clearable=True)
    text_input.set_error("Required")
    assert text_input.has_error
    assert text_input.error_message == "Required"
    assert COLORS["state_danger"] in text_input.styleSheet()
    text_input.clear_error()
    assert not text_input.has_error

    select = ds.Select(
        [("Active", "active"), ("Inactive", "inactive")],
        placeholder="Status",
    )
    assert select.count() == 3
    select.set_error("Choose a status")
    assert select.has_error
    assert COLORS["state_danger"] in select.styleSheet()
    select.clear_error()
    assert not select.has_error


def test_badge_card_toolbar_and_tabs(app):
    badge = ds.Badge.from_status("ACTIVE")
    assert badge.text() == "Active"
    assert badge.height() == COMPONENT_METRICS["badge_height"]

    card = ds.Card("Profile", "Student overview", elevation="sm")
    child = QLabel("Content")
    card.add_widget(child)
    assert card.content_layout.count() == 1
    assert card.graphicsEffect() is not None

    toolbar = ds.Toolbar()
    start = QLabel("Students")
    toolbar.add_widget(start)
    action = toolbar.add_action("Add student")
    assert toolbar.start_zone.count() == 1
    assert toolbar.end_zone.count() == 1
    assert isinstance(action, ds.Button)

    tabs = ds.Tabs()
    page = QWidget()
    index = tabs.add_page(page, "Overview")
    assert index == 0
    assert tabs.widget(0) is page


def test_dialog_and_state_components(app):
    dialog = ds.Dialog("Edit student", description="Update profile details")
    dialog.add_body_widget(ds.Input("Full name"))
    assert dialog.body_layout.count() == 1
    assert dialog.minimumWidth() == COMPONENT_METRICS["dialog_min_width"]

    empty = ds.EmptyState(
        title="No students",
        description="Students will appear here.",
        action_text="Add student",
    )
    assert empty.title_label.text() == "No students"
    assert empty.action_button is not None

    loading = ds.LoadingState("Loading students")
    assert loading.layout().count() >= 1

    error = ds.ErrorState(description="Could not load students")
    assert error.action_button is not None


def test_shared_state_components_are_foundation_backed(app):
    assert SharedEmptyState is ds.EmptyState
    assert SharedErrorState is ds.ErrorState

    skeleton = LoadingSkeleton()
    assert isinstance(skeleton, ds.Skeleton)

    loading = LoadingWidget(count=3)
    assert isinstance(loading, ds.LoadingState)
    assert loading.layout().count() == 4
