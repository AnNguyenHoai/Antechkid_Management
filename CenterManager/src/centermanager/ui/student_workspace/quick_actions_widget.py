# -*- coding: utf-8 -*-
"""Student detail actions with explicit write-state feedback."""
from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from centermanager.ui.design_system import (
    Button,
    ButtonVariant,
    ComponentSize,
    EditStateBanner,
)
from centermanager.ui.design_system.tokens import SPACING


class QuickActionsWidget(QWidget):
    export_pdf_clicked = Signal()
    upload_photo_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["sm"])

        self.edit_state_banner = EditStateBanner("readonly", parent=self)
        root.addWidget(self.edit_state_banner)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])

        self.edit_btn = Button(
            "Edit",
            variant=ButtonVariant.PRIMARY,
            size=ComponentSize.SMALL,
        )
        self.add_parent_btn = Button(
            "Add parent",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )
        self.add_assessment_btn = Button(
            "Add assessment",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )
        self.add_note_btn = Button(
            "Add note",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )
        self.upload_doc_btn = Button(
            "Upload document",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )
        self.upload_photo_btn = Button(
            "Photo",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )
        self.export_pdf_btn = Button(
            "Export PDF",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
        )

        for btn in [
            self.edit_btn,
            self.add_parent_btn,
            self.add_assessment_btn,
            self.add_note_btn,
            self.upload_doc_btn,
            self.upload_photo_btn,
            self.export_pdf_btn,
        ]:
            layout.addWidget(btn)
        layout.addStretch()
        root.addLayout(layout)

        self.export_pdf_btn.clicked.connect(self.export_pdf_clicked.emit)
        self.upload_photo_btn.clicked.connect(self.upload_photo_clicked.emit)

    def set_actions(
        self,
        on_edit: Callable,
        on_add_parent: Callable,
        on_add_assessment: Callable,
        on_add_note: Callable,
        on_upload_doc: Callable,
        on_export_pdf: Optional[Callable] = None,
        on_upload_photo: Optional[Callable] = None,
    ) -> None:
        self.edit_btn.clicked.connect(on_edit)
        self.add_parent_btn.clicked.connect(on_add_parent)
        self.add_assessment_btn.clicked.connect(on_add_assessment)
        self.add_note_btn.clicked.connect(on_add_note)
        self.upload_doc_btn.clicked.connect(on_upload_doc)
        if on_export_pdf:
            self.export_pdf_btn.clicked.connect(on_export_pdf)
        if on_upload_photo:
            self.upload_photo_btn.clicked.connect(on_upload_photo)

    def set_write_enabled(self, enabled: bool) -> None:
        self.edit_state_banner.set_state("editing" if enabled else "readonly")
        self.edit_btn.setEnabled(enabled)
        self.add_parent_btn.setEnabled(enabled)
        self.add_assessment_btn.setEnabled(enabled)
        self.add_note_btn.setEnabled(enabled)
        self.upload_doc_btn.setEnabled(enabled)
        self.upload_photo_btn.setEnabled(enabled)
        # Export PDF is intentionally available in read-only mode.
