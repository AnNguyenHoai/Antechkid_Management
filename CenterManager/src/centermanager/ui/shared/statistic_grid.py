# -*- coding: utf-8 -*-
"""
StatisticGrid - Grid layout for metric cards.
"""
from typing import Optional, List, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QSizePolicy

from centermanager.ui.shared.metric_card import MetricCard
from centermanager.ui.design_system.tokens import SPACING


class StatisticGrid(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setSpacing(SPACING['md'])  # Tăng từ 12 lên 16
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._cards = []

    def set_metrics(self, metrics: List[Dict[str, str]], columns: int = 4) -> None:
        self._clear()
        row, col = 0, 0
        for metric in metrics:
            card = MetricCard(
                icon=metric.get('icon', '📊'),
                label=metric.get('label', ''),
                value=metric.get('value', '0'),
                sub_value=metric.get('sub_value', None)
            )
            self._layout.addWidget(card, row, col)
            self._cards.append(card)
            col += 1
            if col >= columns:
                col = 0
                row += 1

    def _clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()

    def update_value(self, index: int, value: str) -> None:
        if 0 <= index < len(self._cards):
            self._cards[index].set_value(value)