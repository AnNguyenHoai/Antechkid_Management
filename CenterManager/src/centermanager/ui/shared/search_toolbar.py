# -*- coding: utf-8 -*-
"""Search and filter toolbar for data-heavy operational screens."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from centermanager.ui.design_system.foundation import (
    Button,
    ButtonVariant,
    ComponentSize,
    Input,
    Select,
)
from centermanager.ui.design_system.tokens import COMPONENT_METRICS, SPACING


class SearchToolbar(QWidget):
    """Compact search/filter row with legacy and full-state filter signals.

    ``filter_changed`` retains the historical one-key delta contract. New data-heavy
    pages should prefer ``filters_changed``, which emits the complete filter state.
    """

    search_changed = Signal(str)
    filter_changed = Signal(dict)
    filters_changed = Signal(dict)
    cleared = Signal()

    def __init__(
        self,
        placeholder: str = "Search...",
        filters: Optional[List[Dict[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._filters = filters or []
        self.filter_controls: Dict[str, Select] = {}
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        self.search_input = Input(
            placeholder,
            size=ComponentSize.SMALL,
            clearable=True,
            parent=self,
        )
        self.search_input.setMinimumWidth(COMPONENT_METRICS["data_search_min_width"])
        self.search_input.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.search_input, 1)

        for filter_config in self._filters:
            key = str(filter_config.get("key") or filter_config.get("name") or "").strip()
            if not key:
                continue
            label = str(filter_config.get("label") or filter_config.get("name") or key).strip()
            options = list(filter_config.get("options") or [])
            combo = Select(
                options,
                placeholder="All",
                size=ComponentSize.SMALL,
                parent=self,
            )
            combo.setMinimumWidth(COMPONENT_METRICS["data_filter_min_width"])
            combo.setAccessibleName(label)
            combo.setToolTip(label)
            combo.currentTextChanged.connect(
                lambda text, filter_key=key: self._on_filter_changed(filter_key, text)
            )
            self.filter_controls[key] = combo
            layout.addWidget(combo)

        self.clear_btn = Button(
            "Clear",
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=self,
        )
        self.clear_btn.setToolTip("Clear search and filters")
        self.clear_btn.clicked.connect(self.clear)
        layout.addWidget(self.clear_btn)

    def _on_filter_changed(self, key: str, text: str) -> None:
        combo = self.filter_controls[key]
        value = text if combo.currentIndex() > 0 else ""
        self.filter_changed.emit({key: value})
        self.filters_changed.emit(self.filters())

    def filters(self) -> Dict[str, str]:
        """Return the complete filter state using stable filter keys."""
        values: Dict[str, str] = {}
        for key, combo in self.filter_controls.items():
            values[key] = combo.currentText() if combo.currentIndex() > 0 else ""
        return values

    def set_filter_value(self, key: str, value: str) -> None:
        combo = self.filter_controls.get(key)
        if combo is None:
            raise KeyError(key)
        if not value:
            combo.setCurrentIndex(0)
            return
        index = combo.findText(value)
        if index < 0:
            raise ValueError(f"Unknown value for {key}: {value}")
        combo.setCurrentIndex(index)

    def clear(self) -> None:
        self.search_input.clear()
        changed = False
        for combo in self.filter_controls.values():
            if combo.currentIndex() != 0:
                changed = True
                combo.setCurrentIndex(0)
        if not changed:
            self.filters_changed.emit(self.filters())
        self.cleared.emit()

    def text(self) -> str:
        return self.search_input.text()

    def setText(self, text: str) -> None:
        """Compatibility helper matching the legacy SearchBar naming style."""
        self.search_input.setText(text)

    def setPlaceholderText(self, text: str) -> None:
        """Compatibility helper for pages migrating from SearchBar."""
        self.search_input.setPlaceholderText(text)


__all__ = ["SearchToolbar"]
