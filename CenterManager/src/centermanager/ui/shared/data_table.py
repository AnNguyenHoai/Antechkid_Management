# -*- coding: utf-8 -*-
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QComboBox, QAbstractItemView,
    QFrame
)

from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY


class DataTable(QWidget):
    selection_changed = Signal(list)  # list of selected row indices
    sort_requested = Signal(str, bool)  # column, ascending
    row_double_clicked = Signal(int)  # row index
    context_menu_requested = Signal(QPoint, int)  # global position, row

    def __init__(
        self,
        columns: List[Dict[str, str]],
        parent: Optional[QWidget] = None,
        page_size: int = 20,
    ) -> None:
        super().__init__(parent)
        self._columns = columns
        self._page_size = page_size
        self._current_page = 0
        self._total_rows = 0
        self._data = []
        self._selected_rows = set()
        self._sort_column = None
        self._sort_ascending = True

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._columns))
        self.table.setHorizontalHeaderLabels([c['label'] for c in self._columns])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSortingEnabled(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        layout.addWidget(self.table)

        pagination = QHBoxLayout()
        pagination.setSpacing(SPACING['sm'])
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedWidth(60)
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedWidth(60)
        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet(f"font-size: {TYPOGRAPHY['body']}px;")
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["10", "20", "50", "100"])
        self.page_size_combo.setCurrentText(str(self._page_size))
        pagination.addWidget(self.prev_btn)
        pagination.addWidget(self.page_label)
        pagination.addWidget(self.next_btn)
        pagination.addStretch()
        pagination.addWidget(QLabel("Rows per page:"))
        pagination.addWidget(self.page_size_combo)
        layout.addLayout(pagination)

    def _connect_signals(self) -> None:
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.table.horizontalHeader().sectionClicked.connect(self._on_sort)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda idx: self.row_double_clicked.emit(idx.row()))
        self.table.customContextMenuRequested.connect(self._on_context_menu)

    def set_data(self, data: List[Dict[str, Any]], total: int) -> None:
        self._data = data
        self._total_rows = total
        self._current_page = 0
        self._update_table()

    def _update_table(self) -> None:
        start = self._current_page * self._page_size
        end = min(start + self._page_size, len(self._data))
        page_data = self._data[start:end]
        self.table.setRowCount(len(page_data))
        self.table.setColumnCount(len(self._columns))

        for row, item in enumerate(page_data):
            for col, col_def in enumerate(self._columns):
                key = col_def['key']
                value = item.get(key, "")
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, cell)

        total_pages = (self._total_rows + self._page_size - 1) // self._page_size
        self.page_label.setText(f"Page {self._current_page + 1} of {max(1, total_pages)}")
        self.prev_btn.setEnabled(self._current_page > 0)
        self.next_btn.setEnabled(self._current_page < total_pages - 1)

    def _prev_page(self) -> None:
        if self._current_page > 0:
            self._current_page -= 1
            self._update_table()

    def _next_page(self) -> None:
        total_pages = (self._total_rows + self._page_size - 1) // self._page_size
        if self._current_page < total_pages - 1:
            self._current_page += 1
            self._update_table()

    def _on_page_size_changed(self, size: str) -> None:
        self._page_size = int(size)
        self._current_page = 0
        self._update_table()

    def _on_sort(self, col: int) -> None:
        if col < len(self._columns) and self._columns[col].get('sortable', False):
            if self._sort_column == col:
                self._sort_ascending = not self._sort_ascending
            else:
                self._sort_column = col
                self._sort_ascending = True
            key = self._columns[col]['key']
            self.sort_requested.emit(key, self._sort_ascending)

    def _on_selection_changed(self) -> None:
        selected = set()
        for item in self.table.selectedItems():
            selected.add(item.row())
        self._selected_rows = selected
        self.selection_changed.emit(list(selected))

    def _on_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if index.isValid():
            self.context_menu_requested.emit(self.table.mapToGlobal(pos), index.row())

    def clear_selection(self) -> None:
        self.table.clearSelection()
        self._selected_rows.clear()