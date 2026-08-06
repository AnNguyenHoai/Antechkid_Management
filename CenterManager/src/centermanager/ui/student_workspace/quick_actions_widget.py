# -*- coding: utf-8 -*-
"""
QuickActionsWidget - quick action buttons for student detail.
"""
from typing import Optional, Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS
from centermanager.ui.design_system.components import PrimaryButton, SecondaryButton


class QuickActionsWidget(QWidget):
    export_pdf_clicked = Signal()  # NEW

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        self.edit_btn = PrimaryButton("✏️ Edit")
        self.add_parent_btn = SecondaryButton("👨‍👩‍👧 Add Parent")
        self.add_assessment_btn = SecondaryButton("📊 Add Assessment")
        self.add_note_btn = SecondaryButton("📝 Add Note")
        self.upload_doc_btn = SecondaryButton("📎 Upload Doc")
        self.export_pdf_btn = SecondaryButton("📄 Export PDF")  # NEW

        for btn in [self.edit_btn, self.add_parent_btn, self.add_assessment_btn,
                    self.add_note_btn, self.upload_doc_btn, self.export_pdf_btn]:
            btn.setFixedHeight(34)
            btn.setMinimumWidth(120)

        layout.addWidget(self.edit_btn)
        layout.addWidget(self.add_parent_btn)
        layout.addWidget(self.add_assessment_btn)
        layout.addWidget(self.add_note_btn)
        layout.addWidget(self.upload_doc_btn)
        layout.addWidget(self.export_pdf_btn)  # NEW
        layout.addStretch()

        # Connect new button
        self.export_pdf_btn.clicked.connect(self.export_pdf_clicked.emit)

    def set_actions(
        self,
        on_edit: Callable,
        on_add_parent: Callable,
        on_add_assessment: Callable,
        on_add_note: Callable,
        on_upload_doc: Callable,
        on_export_pdf: Optional[Callable] = None,  # NEW
    ) -> None:
        self.edit_btn.clicked.connect(on_edit)
        self.add_parent_btn.clicked.connect(on_add_parent)
        self.add_assessment_btn.clicked.connect(on_add_assessment)
        self.add_note_btn.clicked.connect(on_add_note)
        self.upload_doc_btn.clicked.connect(on_upload_doc)
        if on_export_pdf:
            self.export_pdf_btn.clicked.connect(on_export_pdf)
    def set_write_enabled(self, enabled: bool) -> None:
        self.edit_btn.setEnabled(enabled)
        self.add_parent_btn.setEnabled(enabled)
        self.add_assessment_btn.setEnabled(enabled)
        self.add_note_btn.setEnabled(enabled)
        self.upload_doc_btn.setEnabled(enabled)
        # export PDF luôn enabled vì là read-only