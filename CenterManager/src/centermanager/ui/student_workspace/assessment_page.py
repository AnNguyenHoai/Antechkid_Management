# -*- coding: utf-8 -*-
"""
AssessmentPage - placeholder for assessment management.
"""
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from centermanager.ui.common.empty_state import EmptyState


class AssessmentPage(QWidget):
    def __init__(self, assessment_service, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        empty = EmptyState(
            icon="📋",
            title="Assessment Management",
            description="Assessment management will be available here."
        )
        layout.addWidget(empty)