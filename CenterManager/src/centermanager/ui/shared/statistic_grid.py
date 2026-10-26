# -*- coding: utf-8 -*-
"""Responsive grid for shared workspace KPI cards."""
from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import QGridLayout, QWidget

from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.shared.metric_card import MetricCard


class StatisticGrid(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setHorizontalSpacing(SPACING["md"])
        self._layout.setVerticalSpacing(SPACING["md"])
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._cards: list[MetricCard] = []

    def set_metrics(
        self,
        metrics: List[Dict[str, str]],
        columns: Optional[int] = None,
    ) -> None:
        """Render metrics using a balanced column count unless explicitly supplied."""
        self._clear()
        if not metrics:
            return

        resolved_columns = max(
            1,
            min(
                int(columns) if columns is not None else min(len(metrics), 4),
                len(metrics),
            ),
        )
        for column in range(resolved_columns):
            self._layout.setColumnStretch(column, 1)

        for index, metric in enumerate(metrics):
            row = index // resolved_columns
            column = index % resolved_columns
            card = MetricCard(
                icon=metric.get("icon", "•"),
                label=metric.get("label", ""),
                value=metric.get("value", "0"),
                sub_value=metric.get("sub_value"),
                tone=metric.get("tone", "neutral"),
                compact=bool(metric.get("compact", False)),
                parent=self,
            )
            self._layout.addWidget(card, row, column)
            self._cards.append(card)

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

    def update_value(self, index: int, value: str) -> None:
        if 0 <= index < len(self._cards):
            self._cards[index].set_value(value)


__all__ = ["StatisticGrid"]
