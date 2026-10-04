from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


@dataclass(frozen=True)
class EmployeeTableColumn:
    """Presentation contract for dense employee workspace tables."""

    mode: str = "fixed"  # fixed | contents | stretch
    width: Optional[int] = None
    alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter


def configure_employee_table(
    table: QTableWidget,
    columns: list[EmployeeTableColumn],
    *,
    row_height: int = 36,
    minimum_height: int = 180,
) -> None:
    """Apply one predictable sizing/alignment contract across Employee tables.

    Tables keep their semantic columns readable at a glance, reserve stretch
    space for descriptive text, and avoid repeated resizeColumnsToContents()
    calls that make widths jump after every refresh.
    """

    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setTextElideMode(Qt.TextElideMode.ElideRight)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(row_height)
    table.verticalHeader().setMinimumSectionSize(row_height)
    table.setMinimumHeight(minimum_height)

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setMinimumSectionSize(72)

    for index, spec in enumerate(columns):
        if spec.mode == "stretch":
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        elif spec.mode == "contents":
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        else:
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
            if spec.width:
                table.setColumnWidth(index, spec.width)


def set_employee_cell(
    table: QTableWidget,
    row: int,
    column: int,
    value,
    *,
    alignment: Optional[Qt.AlignmentFlag] = None,
    user_data=None,
) -> QTableWidgetItem:
    """Create a consistently aligned cell and preserve full text as a tooltip."""

    text = "" if value is None else str(value)
    item = QTableWidgetItem(text)
    item.setToolTip(text)
    if alignment is not None:
        item.setTextAlignment(alignment)
    if user_data is not None:
        item.setData(Qt.ItemDataRole.UserRole, user_data)
    table.setItem(row, column, item)
    return item


def set_employee_row(
    table: QTableWidget,
    row: int,
    values: list,
    columns: list[EmployeeTableColumn],
    *,
    row_user_data=None,
) -> None:
    for column, value in enumerate(values):
        user_data = row_user_data if column == 0 else None
        set_employee_cell(
            table,
            row,
            column,
            value,
            alignment=columns[column].alignment,
            user_data=user_data,
        )
