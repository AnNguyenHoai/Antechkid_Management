# -*- coding: utf-8 -*-
"""
TimelinePage - placeholder for timeline management.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout

from centermanager.ui.common.empty_state import EmptyState


class TimelinePage(QWidget):
    def __init__(self, timeline_service, student_service, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        empty = EmptyState(
            icon="📅",
            title="Timeline",
            description="Timeline management will be available here."
        )
        layout.addWidget(empty)