# -*- coding: utf-8 -*-
"""Shared UI components for all workspaces."""
from PySide6.QtWidgets import QHeaderView

from .metric_card import MetricCard
from .statistic_grid import StatisticGrid
from .activity_card import ActivityCard
from .timeline_card import TimelineCard
from .warning_banner import WarningBanner
from .empty_state import EmptyState
from .error_state import ErrorState
from .section_header import SectionHeader
from .search_toolbar import SearchToolbar
from .loading_widget import LoadingWidget, LoadingSkeleton
from .data_table import BulkActionBar, DataTable as _DataTable, TableDensity
from .chart_card import ChartCard


class DataTable(_DataTable):
    """Workspace default table with evenly distributed visible columns.

    The base table keeps ``Interactive`` sizing for low-level callers that need
    custom widths. Workspace imports use this shared facade so operational tables
    do not bunch columns on the left and leave one oversized final column.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)


__all__ = [
    "MetricCard",
    "StatisticGrid",
    "ActivityCard",
    "TimelineCard",
    "WarningBanner",
    "EmptyState",
    "ErrorState",
    "SectionHeader",
    "SearchToolbar",
    "LoadingWidget",
    "LoadingSkeleton",
    "BulkActionBar",
    "DataTable",
    "TableDensity",
    "ChartCard",
]
