# -*- coding: utf-8 -*-
"""Regression coverage for UI-PROD-05 data-heavy UX."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from centermanager.ui.design_system.foundation import ButtonVariant
from centermanager.ui.design_system.tokens import COMPONENT_METRICS
from centermanager.ui.shared import (
    BulkActionBar,
    DataTable,
    SearchToolbar,
    TableDensity,
)


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


def _rows(count: int):
    return [{"code": f"S{index:03d}", "name": f"Student {index}"} for index in range(count)]


def _columns():
    return [
        {"key": "code", "label": "Code", "sortable": True},
        {"key": "name", "label": "Name", "sortable": True},
    ]


def test_data_table_local_pagination_density_and_result_range(app):
    table = DataTable(
        _columns(),
        page_size=10,
        density=TableDensity.COMPACT,
    )
    table.set_data(_rows(25), 25)

    assert table.current_page == 1
    assert table.page_size == 10
    assert table.total_rows == 25
    assert table.table.rowCount() == 10
    assert table.result_label.text() == "1-10 of 25"
    assert table.table.verticalHeader().defaultSectionSize() == COMPONENT_METRICS[
        "data_table_row_height_compact"
    ]

    table.next_btn.click()

    assert table.current_page == 2
    assert table.result_label.text() == "11-20 of 25"
    assert table.data_index_for_visible_row(0) == 10
    assert table.data_index_for_visible_row(9) == 19

    table.set_density(TableDensity.COMFORTABLE)
    assert table.density == "comfortable"
    assert table.table.verticalHeader().defaultSectionSize() == COMPONENT_METRICS[
        "data_table_row_height_comfortable"
    ]


def test_data_table_server_pagination_contract_is_preserved(app):
    table = DataTable(_columns(), page_size=20)
    requests = []
    table.page_requested.connect(lambda page, size: requests.append((page, size)))
    table.set_server_data(_rows(20), total=45, page=1, page_size=20)

    table.next_btn.click()

    assert requests == [(2, 20)]
    assert table.current_page == 2
    assert table.data_index_for_visible_row(0) == 0


def test_data_table_inline_empty_loading_error_states(app):
    table = DataTable(_columns())
    table.set_data([], 0)
    assert table.content_stack.currentWidget() is table.empty_state

    table.set_loading(True)
    assert table.content_stack.currentWidget() is table.loading_state

    table.set_error("Could not load rows")
    assert table.error_state is not None
    assert table.content_stack.currentWidget() is table.error_state

    table.set_data(_rows(1), 1)
    assert table.content_stack.currentWidget() is table.table


def test_data_table_sort_contract_and_indicator(app):
    table = DataTable(_columns())
    requested = []
    table.sort_requested.connect(lambda key, ascending: requested.append((key, ascending)))

    table._on_sort(1)
    table._on_sort(1)

    assert requested == [("name", True), ("name", False)]
    assert table.table.horizontalHeader().isSortIndicatorShown()


def test_search_toolbar_keeps_delta_signal_and_adds_full_filter_state(app):
    toolbar = SearchToolbar(
        "Search students",
        filters=[
            {"key": "status", "label": "Status", "options": ["Active", "Archived"]},
            {"name": "level", "label": "Level", "options": ["L1", "L2"]},
        ],
    )
    deltas = []
    full_states = []
    toolbar.filter_changed.connect(deltas.append)
    toolbar.filters_changed.connect(full_states.append)

    toolbar.set_filter_value("status", "Active")

    assert deltas[-1] == {"status": "Active"}
    assert full_states[-1] == {"status": "Active", "level": ""}
    assert toolbar.filters() == {"status": "Active", "level": ""}

    toolbar.setText("An")
    assert toolbar.text() == "An"
    toolbar.clear()
    assert toolbar.text() == ""
    assert toolbar.filters() == {"status": "", "level": ""}


def test_bulk_action_bar_is_selection_driven_and_token_component_based(app):
    bar = BulkActionBar()
    called = []
    action = bar.add_action(
        "export",
        "Export selected",
        lambda: called.append(True),
        variant=ButtonVariant.SECONDARY,
    )

    assert bar.isHidden()
    bar.set_selection_count(3)
    assert not bar.isHidden()
    assert bar.count_label.text() == "3 selected"

    action.click()
    assert called == [True]

    bar.set_selection_count(0)
    assert bar.isHidden()


def test_student_list_is_representative_data_heavy_v2_migration():
    source = Path(
        "src/centermanager/ui/student_workspace/student_list_page.py"
    ).read_text(encoding="utf-8")

    assert "SearchToolbar" in source
    assert "BulkActionBar" in source
    assert "TableDensity.COMPACT" in source
    assert "filters_changed.connect" in source
    assert "data_index_for_visible_row" in source
    assert "set_loading" in source
    assert "set_error" in source
    assert "filter_clicked" in source


def test_data_heavy_v2_sources_have_no_raw_colors_emoji_or_legacy_styles():
    paths = [
        Path("src/centermanager/ui/shared/data_table.py"),
        Path("src/centermanager/ui/shared/search_toolbar.py"),
        Path("src/centermanager/ui/student_workspace/student_list_page.py"),
    ]
    raw_hex_pattern = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F900-\U0001F9FF"
        "]"
    )

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert raw_hex_pattern.search(source) is None, path
        assert emoji_pattern.search(source) is None, path
        assert "ui.styles" not in source, path


def test_data_heavy_metrics_are_token_owned():
    expected = {
        "data_table_header_height",
        "data_table_row_height_compact",
        "data_table_row_height_comfortable",
        "data_table_footer_height",
        "data_table_min_column_width",
        "data_bulk_bar_height",
        "data_filter_min_width",
        "data_search_min_width",
    }
    assert expected.issubset(COMPONENT_METRICS)
