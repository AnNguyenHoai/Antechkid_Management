# -*- coding: utf-8 -*-
"""
ReportsPage - placeholder for student reports.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout

from centermanager.ui.common.empty_state import EmptyState


class ReportsPage(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        empty = EmptyState(
            icon="📈",
            title="Student Reports",
            description="Reports and analytics will be available here."
        )
        layout.addWidget(empty)