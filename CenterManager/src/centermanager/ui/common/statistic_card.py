# -*- coding: utf-8 -*-
"""
StatisticCard - a card displaying a single statistic with icon and value.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy

from centermanager.ui import styles


class StatisticCard(QFrame):
    """Statistic card with icon, label, and value."""

    def __init__(
        self,
        icon: str,
        label: str,
        value: str,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._setup_ui(icon, label, value)

    def _setup_ui(self, icon: str, label: str, value: str) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(styles.CARD_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(100)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        # Top row: icon + label
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet(styles.STAT_ICON)
        top_layout.addWidget(icon_label)

        label_label = QLabel(label)
        label_label.setStyleSheet(styles.STAT_LABEL)
        top_layout.addWidget(label_label)
        top_layout.addStretch()

        layout.addLayout(top_layout)

        # Value
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(styles.STAT_VALUE)
        layout.addWidget(self.value_label)

        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)