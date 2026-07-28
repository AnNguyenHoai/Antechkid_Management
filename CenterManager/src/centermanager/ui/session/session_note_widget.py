# -*- coding: utf-8 -*-
"""
SessionNoteWidget - form for creating/editing a session note.
Now with improved empty state and auto-refresh.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, QPlainTextEdit,
    QPushButton, QHBoxLayout, QLabel, QFrame, QMessageBox
)

from centermanager.models.session_note import TeachingProgress, ClassAtmosphere, SessionNote
from centermanager.services.session_note_service import SessionNoteService, SessionNoteValidationError

logger = logging.getLogger(__name__)


class SessionNoteWidget(QWidget):
    note_saved = Signal()
    note_deleted = Signal()

    def __init__(
        self,
        note_service: SessionNoteService,
        session_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = note_service
        self._session_id = session_id
        self._note: Optional[SessionNote] = None
        self._is_edit_mode = False

        self._setup_ui()
        self._load_note()

    def _setup_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # Stacked widget to switch between empty state and form
        self.stacked = QStackedWidget()
        self.main_layout.addWidget(self.stacked)

        # --- Empty State ---
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)

        icon = QLabel("📝")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        empty_layout.addWidget(icon)

        title = QLabel("No Teaching Note Yet")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        empty_layout.addWidget(title)

        desc = QLabel("Write today's teaching reflection.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 14px;")
        empty_layout.addWidget(desc)

        self.create_btn = QPushButton("+ Create Note")
        self.create_btn.setFixedWidth(140)
        self.create_btn.clicked.connect(self._show_form)
        empty_layout.addWidget(self.create_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked.addWidget(empty_widget)

        # --- Edit Form ---
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        self.form = QFormLayout()
        self.form.setSpacing(6)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Teaching Progress
        self.teaching_combo = QComboBox()
        for val in TeachingProgress.choices():
            self.teaching_combo.addItem(val)
        self.form.addRow("Teaching Progress *", self.teaching_combo)

        # Class Atmosphere
        self.atmosphere_combo = QComboBox()
        for val in ClassAtmosphere.choices():
            self.atmosphere_combo.addItem(val)
        self.form.addRow("Class Atmosphere *", self.atmosphere_combo)

        # Difficulties
        self.difficulties_edit = QPlainTextEdit()
        self.difficulties_edit.setPlaceholderText("Difficulties encountered (optional)")
        self.difficulties_edit.setMaximumHeight(80)
        self.form.addRow("Difficulties", self.difficulties_edit)

        # Next Plan
        self.next_plan_edit = QPlainTextEdit()
        self.next_plan_edit.setPlaceholderText("Plan for next session (optional)")
        self.next_plan_edit.setMaximumHeight(80)
        self.form.addRow("Next Plan", self.next_plan_edit)

        # Remark
        self.remark_edit = QPlainTextEdit()
        self.remark_edit.setPlaceholderText("Additional remarks (optional)")
        self.remark_edit.setMaximumHeight(80)
        self.form.addRow("Remark", self.remark_edit)

        form_layout.addLayout(self.form)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.delete_btn = QPushButton("Delete Note")
        self.delete_btn.setFixedWidth(120)
        self.delete_btn.setStyleSheet("color: #d32f2f;")
        self.delete_btn.setVisible(False)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.clicked.connect(self._load_note)  # reload to return to summary
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.delete_btn)
        form_layout.addLayout(btn_layout)

        self.stacked.addWidget(form_widget)

        self.save_btn.clicked.connect(self._save)
        self.delete_btn.clicked.connect(self._delete)

        # Default: show empty
        self.stacked.setCurrentIndex(0)

    def _load_note(self) -> None:
        """Load existing note if any."""
        try:
            self._note = self._service.get_note(self._session_id)
            if self._note:
                self._is_edit_mode = True
                self._populate_form(self._note)
                self.delete_btn.setVisible(True)
                self.stacked.setCurrentIndex(1)  # show form
            else:
                self._is_edit_mode = False
                self._clear_form()
                self.delete_btn.setVisible(False)
                self.stacked.setCurrentIndex(0)  # show empty
        except Exception as e:
            logger.exception("Error loading session note")
            # Show empty state with error message?
            self.stacked.setCurrentIndex(0)

    def _populate_form(self, note: SessionNote) -> None:
        idx = self.teaching_combo.findText(note.teaching_progress)
        if idx >= 0:
            self.teaching_combo.setCurrentIndex(idx)
        idx2 = self.atmosphere_combo.findText(note.class_atmosphere)
        if idx2 >= 0:
            self.atmosphere_combo.setCurrentIndex(idx2)
        self.difficulties_edit.setPlainText(note.difficulties or "")
        self.next_plan_edit.setPlainText(note.next_plan or "")
        self.remark_edit.setPlainText(note.remark or "")

    def _clear_form(self) -> None:
        self.teaching_combo.setCurrentIndex(0)
        self.atmosphere_combo.setCurrentIndex(0)
        self.difficulties_edit.clear()
        self.next_plan_edit.clear()
        self.remark_edit.clear()

    def _show_form(self) -> None:
        self._clear_form()
        self.delete_btn.setVisible(False)
        self._is_edit_mode = False
        self.stacked.setCurrentIndex(1)

    def _save(self) -> None:
        teaching = self.teaching_combo.currentText()
        atmosphere = self.atmosphere_combo.currentText()
        difficulties = self.difficulties_edit.toPlainText().strip() or None
        next_plan = self.next_plan_edit.toPlainText().strip() or None
        remark = self.remark_edit.toPlainText().strip() or None

        try:
            if self._is_edit_mode and self._note:
                self._service.update_note(
                    session_id=self._session_id,
                    teaching_progress=teaching,
                    class_atmosphere=atmosphere,
                    difficulties=difficulties,
                    next_plan=next_plan,
                    remark=remark,
                )
                QMessageBox.information(self, "Success", "Teaching Note updated.")
            else:
                self._service.create_note(
                    session_id=self._session_id,
                    teaching_progress=teaching,
                    class_atmosphere=atmosphere,
                    difficulties=difficulties,
                    next_plan=next_plan,
                    remark=remark,
                )
                QMessageBox.information(self, "Success", "Teaching Note created.")
                self._is_edit_mode = True

            # Refresh to show note
            self._load_note()
            self.note_saved.emit()
        except SessionNoteValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving note")
            QMessageBox.critical(self, "Error", "Could not save teaching note.")

    def _delete(self) -> None:
        if not self._note:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this teaching note? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_note(self._session_id)
                self._note = None
                self._is_edit_mode = False
                self._clear_form()
                self.delete_btn.setVisible(False)
                self.stacked.setCurrentIndex(0)
                QMessageBox.information(self, "Deleted", "Teaching note deleted.")
                self.note_deleted.emit()
            except Exception as e:
                logger.exception("Error deleting note")
                QMessageBox.critical(self, "Error", "Could not delete teaching note.")

    def set_session(self, session_id: int) -> None:
        """Allow external refresh."""
        self._session_id = session_id
        self._load_note()