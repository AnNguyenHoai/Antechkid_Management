# -*- coding: utf-8 -*-
"""
ParentCard widget - displays a single parent with Edit/Delete buttons.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QSizePolicy
)

from centermanager.models.parent import Parent


class ParentCard(QFrame):
    """Card displaying parent information with action buttons."""
    edit_clicked = Signal(int)      # parent_id
    delete_clicked = Signal(int)    # parent_id

    def __init__(self, parent: Parent, parent_widget=None) -> None:
        super().__init__(parent_widget)
        self._parent = parent
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 6px;
                background: white;
                padding: 8px 12px;
                margin: 4px 0;
            }
        """)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header row: name + relationship + buttons
        header = QHBoxLayout()
        name_label = QLabel(self._parent.name or "-")
        name_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        header.addWidget(name_label)

        rel_label = QLabel(self._parent.relation_type or "")
        rel_label.setStyleSheet("color: #666; font-size: 13px;")
        header.addWidget(rel_label)
        header.addStretch()

        # Edit & Delete buttons
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setFixedWidth(50)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedWidth(60)
        self.delete_btn.setStyleSheet("color: #d32f2f;")
        header.addWidget(self.edit_btn)
        header.addWidget(self.delete_btn)
        layout.addLayout(header)

        # Fields: phone, email, occupation, notes
        fields = QVBoxLayout()
        fields.setSpacing(2)

        if self._parent.phone:
            fields.addWidget(self._create_field("Phone", self._parent.phone))
        if self._parent.email:
            fields.addWidget(self._create_field("Email", self._parent.email))
        if self._parent.occupation:
            fields.addWidget(self._create_field("Occupation", self._parent.occupation))
        if self._parent.notes:
            fields.addWidget(self._create_field("Notes", self._parent.notes))

        layout.addLayout(fields)

        # Connect signals
        self.edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._parent.id))
        self.delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self._parent.id))

    def _create_field(self, label: str, value: str) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label_w = QLabel(f"{label}:")
        label_w.setStyleSheet("font-size: 12px; color: #555;")
        value_w = QLabel(value)
        value_w.setStyleSheet("font-size: 13px; color: #222;")
        layout.addWidget(label_w)
        layout.addWidget(value_w)
        layout.addStretch()
        return w