# -*- coding: utf-8 -*-
"""Compact summary bar for filtered data-heavy lists."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from centermanager.ui.design_system.tokens import (
    COLORS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)


class FilterSummaryBar(QFrame):
    """Shows filtered row count and an aggregate amount without looking like a table row."""

    def __init__(
        self,
        *,
        amount_label: str,
        currency: str = "VND",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FilterSummaryBar")
        self._amount_label = amount_label
        self._currency = currency
        self.setMinimumHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"])
        layout.setSpacing(SPACING["md"])

        self.count_label = QLabel("0 giao dịch phù hợp", self)
        self.count_label.setObjectName("FilterSummaryCount")
        layout.addWidget(self.count_label)

        layout.addStretch()

        self.amount_caption = QLabel(amount_label, self)
        self.amount_caption.setObjectName("FilterSummaryCaption")
        layout.addWidget(self.amount_caption)

        self.amount_value = QLabel("0 VND", self)
        self.amount_value.setObjectName("FilterSummaryAmount")
        self.amount_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.amount_value)

        self.setStyleSheet(
            f"""
            QFrame#FilterSummaryBar {{
                background: {COLORS['surface_card']};
                border-top: 1px solid {COLORS['border_default']};
                border-bottom: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['sm']}px;
            }}
            QLabel#FilterSummaryCount,
            QLabel#FilterSummaryCaption {{
                background: transparent;
                border: none;
                color: {COLORS['text_muted']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
            }}
            QLabel#FilterSummaryAmount {{
                background: transparent;
                border: none;
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['bold']};
            }}
            """
        )

    def set_summary(self, count: int, amount) -> None:
        self.count_label.setText(f"{int(count):,} giao dịch phù hợp")
        value = Decimal(str(amount or 0))
        self.amount_value.setText(f"{value:,.0f} {self._currency}")


__all__ = ["FilterSummaryBar"]
