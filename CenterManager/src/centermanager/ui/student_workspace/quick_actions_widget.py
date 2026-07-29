# -*- coding: utf-8 -*-
"""
QuickActionsWidget - quick action buttons for student detail.
"""
from typing import Optional, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy

from centermanager.ui.design_system.components import PrimaryButton, SecondaryButton


class QuickActionsWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.edit_btn = PrimaryButton("✏️ Edit")
        self.add_parent_btn = SecondaryButton("👨‍👩‍👧 Add Parent")
        self.add_assessment_btn = SecondaryButton("📊 Add Assessment")
        self.add_note_btn = SecondaryButton("📝 Add Note")
        self.upload_doc_btn = SecondaryButton("📎 Upload Doc")

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.add_parent_btn)
        layout.addWidget(self.add_assessment_btn)
        layout.addWidget(self.add_note_btn)
        layout.addWidget(self.upload_doc_btn)
        layout.addStretch()

    def set_actions(
        self,
        on_edit: Callable,
        on_add_parent: Callable,
        on_add_assessment: Callable,
        on_add_note: Callable,
        on_upload_doc: Callable
    ) -> None:
        self.edit_btn.clicked.connect(on_edit)
        self.add_parent_btn.clicked.connect(on_add_parent)
        self.add_assessment_btn.clicked.connect(on_add_assessment)
        self.add_note_btn.clicked.connect(on_add_note)
        self.upload_doc_btn.clicked.connect(on_upload_doc)