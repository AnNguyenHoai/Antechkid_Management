# -*- coding: utf-8 -*-
"""Shared data-heavy table primitives for operational workspaces."""
from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from centermanager.ui.design_system.foundation import (
    Button,
    ButtonVariant,
    ComponentSize,
    EmptyState,
    ErrorState,
    LoadingState,
    Select,
)
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class TableDensity(str, Enum):
    """Supported row-density presets for operational tables."""

    COMPACT = "compact"
    COMFORTABLE = "comfortable"


class BulkActionBar(QFrame):
    """Reusable selection-aware bulk action strip."""

    clear_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DataBulkActionBar")
        self.setMinimumHeight(COMPONENT_METRICS["data_bulk_bar_height"])
        self._actions: Dict[str, Button] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"]
        )
        layout.setSpacing(SPACING["sm"])

        self.count_label = QLabel("0 selected", self)
        self.count_label.setObjectName("DataBulkSelectionCount")
        layout.addWidget(self.count_label)
        layout.addStretch()
        self.actions_layout = layout

        self.clear_button = Button(
            "Clear selection",
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=self,
        )
        self.clear_button.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.clear_button)

        self.setStyleSheet(
            f"""
            QFrame#DataBulkActionBar {{
                background-color: {COLORS["blue_50"]};
                border: none;
                border-bottom: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
            }}
            QLabel#DataBulkSelectionCount {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            """
        )
        self.set_selection_count(0)

    def add_action(
        self,
        key: str,
        text: str,
        callback: Optional[Callable[[], None]] = None,
        *,
        variant: Union[ButtonVariant, str] = ButtonVariant.SECONDARY,
    ) -> Button:
        """Add a named action before the always-last clear action."""
        button = Button(
            text,
            variant=variant,
            size=ComponentSize.SMALL,
            parent=self,
        )
        if callback is not None:
            button.clicked.connect(callback)
        self._actions[key] = button
        self.actions_layout.insertWidget(self.actions_layout.count() - 1, button)
        return button

    def action(self, key: str) -> Optional[Button]:
        return self._actions.get(key)

    def set_selection_count(self, count: int) -> None:
        count = max(0, int(count))
        self.count_label.setText(f"{count} selected")
        self.setVisible(count > 0)


class DataTable(QWidget):
    """Token-driven table with compatible local/server pagination contracts."""

    selection_changed = Signal(list)
    sort_requested = Signal(str, bool)
    row_double_clicked = Signal(int)
    context_menu_requested = Signal(QPoint, int)
    # 1-based page number, page size. Existing users remain local-paginated
    # unless they explicitly call set_server_data().
    page_requested = Signal(int, int)

    def __init__(
        self,
        columns: List[Dict[str, Any]],
        parent: Optional[QWidget] = None,
        page_size: int = 20,
        *,
        density: Union[TableDensity, str] = TableDensity.COMFORTABLE,
        empty_title: str = "No results",
        empty_message: str = "No records match the current view.",
    ) -> None:
        super().__init__(parent)
        self._columns = columns
        self._page_size = max(1, int(page_size))
        self._current_page = 0
        self._total_rows = 0
        self._data: List[Dict[str, Any]] = []
        self._selected_rows = set()
        self._sort_column: Optional[int] = None
        self._sort_ascending = True
        self._server_side = False
        self._density = self._normalize_density(density)
        self._empty_title = empty_title
        self._empty_message = empty_message

        self._setup_ui()
        self._connect_signals()
        self.set_density(self._density)
        self._update_table()

    @staticmethod
    def _normalize_density(density: Union[TableDensity, str]) -> TableDensity:
        if isinstance(density, TableDensity):
            return density
        try:
            return TableDensity(str(density))
        except ValueError as exc:
            raise ValueError(f"Unsupported table density: {density}") from exc

    @property
    def density(self) -> str:
        return self._density.value

    @property
    def current_page(self) -> int:
        """Return the current page as a 1-based value."""
        return self._current_page + 1

    @property
    def page_size(self) -> int:
        return self._page_size

    @property
    def total_rows(self) -> int:
        return self._total_rows

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.content_stack = QStackedWidget(self)
        self.content_stack.setObjectName("DataTableContentStack")

        self.table = QTableWidget(self.content_stack)
        self.table.setObjectName("DataTableGrid")
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels([c["label"] for c in self._columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(
            COMPONENT_METRICS["data_table_min_column_width"]
        )
        self.table.horizontalHeader().setFixedHeight(
            COMPONENT_METRICS["data_table_header_height"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.setStyleSheet(
            f"""
            QTableWidget#DataTableGrid {{
                background-color: {COLORS["surface_page"]};
                alternate-background-color: {COLORS["gray_50"]};
                color: {COLORS["text_primary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["md"]}px;
                selection-background-color: {COLORS["action_primary_selected"]};
                selection-color: {COLORS["action_primary_hover"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
            }}
            QTableWidget#DataTableGrid:focus {{
                border-color: {COLORS["focus_ring"]};
            }}
            QTableWidget#DataTableGrid::item {{
                padding-left: {SPACING["sm"]}px;
                padding-right: {SPACING["sm"]}px;
                border-bottom: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_subtle"]};
            }}
            QTableWidget#DataTableGrid::item:hover {{
                background-color: {COLORS["surface_hover"]};
            }}
            QHeaderView::section {{
                background-color: {COLORS["gray_50"]};
                color: {COLORS["text_secondary"]};
                border: none;
                border-bottom: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                padding-left: {SPACING["sm"]}px;
                padding-right: {SPACING["sm"]}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QHeaderView::section:hover {{
                background-color: {COLORS["surface_hover"]};
            }}
            """
        )
        self.content_stack.addWidget(self.table)

        self.empty_state = EmptyState(
            icon=None,
            title=self._empty_title,
            description=self._empty_message,
            parent=self.content_stack,
        )
        self.content_stack.addWidget(self.empty_state)

        self.loading_state = LoadingState(
            "Loading data...",
            skeleton_rows=5,
            parent=self.content_stack,
        )
        self.content_stack.addWidget(self.loading_state)

        self.error_state: Optional[ErrorState] = None
        layout.addWidget(self.content_stack, 1)

        self.footer = QFrame(self)
        self.footer.setObjectName("DataTableFooter")
        self.footer.setMinimumHeight(COMPONENT_METRICS["data_table_footer_height"])
        pagination = QHBoxLayout(self.footer)
        pagination.setContentsMargins(
            SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["xs"]
        )
        pagination.setSpacing(SPACING["sm"])

        self.result_label = QLabel("0 results", self.footer)
        self.result_label.setObjectName("DataTableResultCount")
        pagination.addWidget(self.result_label)
        pagination.addStretch()

        self.prev_btn = Button(
            "Previous",
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=self.footer,
        )
        self.page_label = QLabel("Page 1 of 1", self.footer)
        self.page_label.setObjectName("DataTablePageLabel")
        self.next_btn = Button(
            "Next",
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=self.footer,
        )
        pagination.addWidget(self.prev_btn)
        pagination.addWidget(self.page_label)
        pagination.addWidget(self.next_btn)

        rows_label = QLabel("Rows per page", self.footer)
        rows_label.setObjectName("DataTableRowsLabel")
        pagination.addWidget(rows_label)
        size_options = ["10", "20", "50", "100"]
        if str(self._page_size) not in size_options:
            size_options.append(str(self._page_size))
        self.page_size_combo = Select(
            size_options,
            size=ComponentSize.SMALL,
            parent=self.footer,
        )
        self.page_size_combo.setCurrentText(str(self._page_size))
        self.page_size_combo.setAccessibleName("Rows per page")
        pagination.addWidget(self.page_size_combo)

        self.footer.setStyleSheet(
            f"""
            QFrame#DataTableFooter {{
                background-color: {COLORS["surface_page"]};
                border: none;
                border-top: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_subtle"]};
            }}
            QLabel#DataTableResultCount,
            QLabel#DataTablePageLabel,
            QLabel#DataTableRowsLabel {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["caption"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )
        layout.addWidget(self.footer)

    def _connect_signals(self) -> None:
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.table.horizontalHeader().sectionClicked.connect(self._on_sort)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda idx: self.row_double_clicked.emit(idx.row()))
        self.table.customContextMenuRequested.connect(self._on_context_menu)

    def set_density(self, density: Union[TableDensity, str]) -> None:
        self._density = self._normalize_density(density)
        metric_key = (
            "data_table_row_height_compact"
            if self._density is TableDensity.COMPACT
            else "data_table_row_height_comfortable"
        )
        self.table.verticalHeader().setDefaultSectionSize(COMPONENT_METRICS[metric_key])
        self.table.verticalHeader().setMinimumSectionSize(COMPONENT_METRICS[metric_key])

    def set_empty_message(self, title: str, message: str = "") -> None:
        self._empty_title = title
        self._empty_message = message
        self.empty_state.title_label.setText(title)
        self.empty_state.message_label.setText(message)
        self.empty_state.message_label.setVisible(bool(message))

    def set_loading(self, loading: bool = True) -> None:
        if loading:
            self.content_stack.setCurrentWidget(self.loading_state)
        elif self.content_stack.currentWidget() is self.loading_state:
            self._show_data_state()

    def set_error(
        self,
        message: str,
        *,
        title: str = "Unable to load data",
        retry_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        if self.error_state is not None:
            self.content_stack.removeWidget(self.error_state)
            self.error_state.deleteLater()
        self.error_state = ErrorState(
            title=title,
            description=message,
            retry_text="Try again" if retry_callback is not None else None,
            retry_callback=retry_callback,
            parent=self.content_stack,
        )
        self.content_stack.addWidget(self.error_state)
        self.content_stack.setCurrentWidget(self.error_state)

    def clear_error(self) -> None:
        if self.error_state is not None:
            self.content_stack.removeWidget(self.error_state)
            self.error_state.deleteLater()
            self.error_state = None
        self._show_data_state()

    def set_data(self, data: List[Dict[str, Any]], total: int) -> None:
        """Legacy/local mode: DataTable owns page slicing."""
        self._server_side = False
        self._data = list(data)
        self._total_rows = max(0, int(total))
        self._current_page = 0
        self._update_table()

    def set_server_data(
        self,
        data: List[Dict[str, Any]],
        total: int,
        page: int,
        page_size: Optional[int] = None,
    ) -> None:
        """Server mode: data contains only the requested page."""
        self._server_side = True
        self._data = list(data)
        self._total_rows = max(0, int(total))
        if page_size is not None:
            self._page_size = max(1, int(page_size))
            if self.page_size_combo.findText(str(self._page_size)) < 0:
                self.page_size_combo.addItem(str(self._page_size))
            if self.page_size_combo.currentText() != str(self._page_size):
                previous = self.page_size_combo.blockSignals(True)
                self.page_size_combo.setCurrentText(str(self._page_size))
                self.page_size_combo.blockSignals(previous)
        self._current_page = max(0, int(page) - 1)
        self._update_table()

    def _update_table(self) -> None:
        if self._server_side:
            page_data = self._data
        else:
            start = self._current_page * self._page_size
            end = min(start + self._page_size, len(self._data))
            page_data = self._data[start:end]

        previous = self.table.blockSignals(True)
        self.table.clearSelection()
        self._selected_rows.clear()
        self.table.setRowCount(len(page_data))
        self.table.setColumnCount(len(self._columns))

        for row, item in enumerate(page_data):
            for col, col_def in enumerate(self._columns):
                key = col_def["key"]
                value = item.get(key, "")
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setToolTip(str(value))
                self.table.setItem(row, col, cell)
        self.table.blockSignals(previous)
        self.selection_changed.emit([])

        total_pages = max(1, (self._total_rows + self._page_size - 1) // self._page_size)
        if self._current_page >= total_pages:
            self._current_page = total_pages - 1
        self.page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self._current_page > 0 and self._total_rows > 0)
        self.next_btn.setEnabled(self._current_page < total_pages - 1 and self._total_rows > 0)
        self._update_result_label()
        self._show_data_state()

    def _update_result_label(self) -> None:
        if self._total_rows <= 0:
            self.result_label.setText("0 results")
            return
        if self._server_side:
            start = self._current_page * self._page_size + 1
            end = min(start + len(self._data) - 1, self._total_rows)
        else:
            start = self._current_page * self._page_size + 1
            end = min(start + self.table.rowCount() - 1, self._total_rows)
        self.result_label.setText(f"{start}-{end} of {self._total_rows}")

    def _show_data_state(self) -> None:
        if self._total_rows <= 0 or self.table.rowCount() <= 0:
            self.content_stack.setCurrentWidget(self.empty_state)
        else:
            self.content_stack.setCurrentWidget(self.table)

    def _prev_page(self) -> None:
        if self._current_page <= 0:
            return
        self._current_page -= 1
        if self._server_side:
            self.page_requested.emit(self._current_page + 1, self._page_size)
            self._update_navigation_only()
        else:
            self._update_table()

    def _next_page(self) -> None:
        total_pages = max(1, (self._total_rows + self._page_size - 1) // self._page_size)
        if self._current_page >= total_pages - 1:
            return
        self._current_page += 1
        if self._server_side:
            self.page_requested.emit(self._current_page + 1, self._page_size)
            self._update_navigation_only()
        else:
            self._update_table()

    def _update_navigation_only(self) -> None:
        """Update server-mode footer while the owner loads the requested page."""
        total_pages = max(1, (self._total_rows + self._page_size - 1) // self._page_size)
        self.page_label.setText(f"Page {self._current_page + 1} of {total_pages}")
        self.prev_btn.setEnabled(self._current_page > 0)
        self.next_btn.setEnabled(self._current_page < total_pages - 1)

    def _on_page_size_changed(self, size: str) -> None:
        if not size:
            return
        self._page_size = max(1, int(size))
        self._current_page = 0
        if self._server_side:
            self.page_requested.emit(1, self._page_size)
            self._update_navigation_only()
        else:
            self._update_table()

    def _on_sort(self, col: int) -> None:
        if col >= len(self._columns) or not self._columns[col].get("sortable", False):
            return
        if self._sort_column == col:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = col
            self._sort_ascending = True
        self.table.horizontalHeader().setSortIndicatorShown(True)
        order = (
            Qt.SortOrder.AscendingOrder
            if self._sort_ascending
            else Qt.SortOrder.DescendingOrder
        )
        self.table.horizontalHeader().setSortIndicator(col, order)
        key = self._columns[col]["key"]
        self.sort_requested.emit(key, self._sort_ascending)

    def _on_selection_changed(self) -> None:
        selected = {item.row() for item in self.table.selectedItems()}
        self._selected_rows = selected
        self.selection_changed.emit(sorted(selected))

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.context_menu_requested.emit(self.table.mapToGlobal(pos), index.row())

    def data_index_for_visible_row(self, row: int) -> int:
        """Map a visible row to the backing local-data index.

        Server-side callers already own only the current page and therefore receive
        the visible row unchanged. This keeps legacy signals page-local while giving
        migrated pages a safe way to address paginated local data.
        """
        if row < 0:
            return -1
        if self._server_side:
            return row
        return self._current_page * self._page_size + row

    def selected_data_indices(self) -> List[int]:
        return [self.data_index_for_visible_row(row) for row in sorted(self._selected_rows)]

    def clear_selection(self) -> None:
        self.table.clearSelection()
        self._selected_rows.clear()


__all__ = ["BulkActionBar", "DataTable", "TableDensity"]
