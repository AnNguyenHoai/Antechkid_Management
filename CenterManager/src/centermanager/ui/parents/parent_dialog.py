# -*- coding: utf-8 -*-
"""
Dialog for adding/editing a parent.
"""
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QCheckBox, QPlainTextEdit
)

from centermanager.models.parent import RelationshipType
from centermanager.services.parent_service import ParentService, ParentValidationError

logger = logging.getLogger(__name__)


class ParentDialog(QDialog):
    """Dialog to create or edit a parent."""

    def __init__(
        self,
        parent_service: ParentService,
        student_id: int,
        parent_id: Optional[int] = None,
        parent_widget=None
    ) -> None:
        super().__init__(parent_widget)
        self._service = parent_service
        self._student_id = student_id
        self._parent_id = parent_id
        self._is_edit = parent_id is not None

        self.setWindowTitle("Edit Parent" if self._is_edit else "Add Parent")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_parent()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Name (required)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Guardian name")
        form.addRow("Name *", self.name_edit)

        # Relationship (dropdown)
        self.relationship_combo = QComboBox()
        self.relationship_combo.addItem("")  # empty
        for rel in RelationshipType.choices():
            self.relationship_combo.addItem(rel)
        form.addRow("Relationship", self.relationship_combo)

        # Phone
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone number")
        form.addRow("Phone", self.phone_edit)

        # Email
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email address")
        form.addRow("Email", self.email_edit)

        # Occupation
        self.occupation_edit = QLineEdit()
        self.occupation_edit.setPlaceholderText("Occupation")
        form.addRow("Occupation", self.occupation_edit)

        # Notes (multiline)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Additional notes (optional)")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Notes", self.notes_edit)

        # Primary contact checkbox
        self.primary_check = QCheckBox("Primary Contact")
        form.addRow("", self.primary_check)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_parent(self) -> None:
        """Load parent data for editing."""
        try:
            parents = self._service.get_parents_for_student(self._student_id)
            parent = next((p for p in parents if p.id == self._parent_id), None)
            if parent is None:
                QMessageBox.warning(self, "Not Found", "Parent not found.")
                self.reject()
                return
            self.name_edit.setText(parent.name or "")
            # Set relationship combo
            idx = self.relationship_combo.findText(parent.relation_type or "")
            if idx >= 0:
                self.relationship_combo.setCurrentIndex(idx)
            self.phone_edit.setText(parent.phone or "")
            self.email_edit.setText(parent.email or "")
            self.occupation_edit.setText(parent.occupation or "")
            self.notes_edit.setPlainText(parent.notes or "")
            self.primary_check.setChecked(parent.is_primary_contact)
        except Exception as e:
            logger.exception("Error loading parent")
            QMessageBox.critical(self, "Error", "Could not load parent data.")
            self.reject()

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        relationship = self.relationship_combo.currentText().strip() or None
        phone = self.phone_edit.text().strip() or None
        email = self.email_edit.text().strip() or None
        occupation = self.occupation_edit.text().strip() or None
        notes = self.notes_edit.toPlainText().strip() or None
        is_primary = self.primary_check.isChecked()

        try:
            if self._is_edit:
                self._service.update_parent(
                    parent_id=self._parent_id,
                    name=name,
                    relationship=relationship,
                    phone=phone,
                    email=email,
                    occupation=occupation,
                    notes=notes,
                    is_primary_contact=is_primary,
                )
            else:
                self._service.create_parent(
                    student_id=self._student_id,
                    name=name,
                    relationship=relationship,
                    phone=phone,
                    email=email,
                    occupation=occupation,
                    notes=notes,
                    is_primary_contact=is_primary,
                )
            self.accept()
        except ParentValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving parent")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")