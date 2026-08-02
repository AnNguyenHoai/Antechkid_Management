# -*- coding: utf-8 -*-
"""
SessionNoteWidget - form for creating/editing a session note.
Header with title and action buttons (Cancel, Save, Delete).
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox,
    QPlainTextEdit, QPushButton, QLabel, QFrame, QMessageBox,
    QStackedWidget, QSizePolicy
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
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # ---- Header: Title + Buttons ----
        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel("📝 Teaching Note")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title_label)

        header.addStretch()

        # Buttons (initially hidden)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_edit)

        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(80)
        self.save_btn.setVisible(False)
        self.save_btn.clicked.connect(self._save)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setFixedWidth(80)
        self.delete_btn.setStyleSheet("color: #d32f2f;")
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self._delete)

        header.addWidget(self.cancel_btn)
        header.addWidget(self.save_btn)
        header.addWidget(self.delete_btn)

        main_layout.addLayout(header)

        # ---- Content area (stacked: empty / form) ----
        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked)

        # Empty state
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(4)

        icon = QLabel("📝")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 28px;")
        empty_layout.addWidget(icon)

        empty_title = QLabel("No Teaching Note Yet")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        empty_layout.addWidget(empty_title)

        desc = QLabel("Write today's teaching reflection.")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #666; font-size: 14px;")
        empty_layout.addWidget(desc)

        self.create_btn = QPushButton("+ Create Note")
        self.create_btn.setFixedWidth(140)
        self.create_btn.clicked.connect(self._show_form)
        empty_layout.addWidget(self.create_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked.addWidget(empty_widget)

        # Form
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        form = QFormLayout()
        form.setSpacing(6)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Teaching Progress
        self.teaching_combo = QComboBox()
        for val in TeachingProgress.choices():
            self.teaching_combo.addItem(val)
        form.addRow("Teaching Progress *", self.teaching_combo)

        # Class Atmosphere
        self.atmosphere_combo = QComboBox()
        for val in ClassAtmosphere.choices():
            self.atmosphere_combo.addItem(val)
        form.addRow("Class Atmosphere *", self.atmosphere_combo)

        # Lesson Content
        self.lesson_content_edit = QPlainTextEdit()
        self.lesson_content_edit.setPlaceholderText("Lesson content (optional)")
        self.lesson_content_edit.setMaximumHeight(80)
        form.addRow("Lesson Content", self.lesson_content_edit)

        # Homework
        self.homework_edit = QPlainTextEdit()
        self.homework_edit.setPlaceholderText("Homework (optional)")
        self.homework_edit.setMaximumHeight(80)
        form.addRow("Homework", self.homework_edit)

        form_layout.addLayout(form)
        self.stacked.addWidget(form_widget)

        self.stacked.setCurrentIndex(0)

    def _load_note(self) -> None:
        """Load existing note if any."""
        try:
            self._note = self._service.get_note(self._session_id)
            if self._note:
                self._is_edit_mode = True
                self._populate_form(self._note)
                self._show_form(edit_mode=True)
            else:
                self._is_edit_mode = False
                self._clear_form()
                self._show_empty()
        except Exception as e:
            logger.exception("Error loading session note")
            self._show_empty()

    def _populate_form(self, note: SessionNote) -> None:
        idx = self.teaching_combo.findText(note.teaching_progress)
        if idx >= 0:
            self.teaching_combo.setCurrentIndex(idx)
        idx2 = self.atmosphere_combo.findText(note.class_atmosphere)
        if idx2 >= 0:
            self.atmosphere_combo.setCurrentIndex(idx2)
        self.lesson_content_edit.setPlainText(note.lesson_content or "")
        self.homework_edit.setPlainText(note.homework or "")

    def _clear_form(self) -> None:
        self.teaching_combo.setCurrentIndex(0)
        self.atmosphere_combo.setCurrentIndex(0)
        self.lesson_content_edit.clear()
        self.homework_edit.clear()

    def _show_empty(self) -> None:
        self.stacked.setCurrentIndex(0)
        self.cancel_btn.setVisible(False)
        self.save_btn.setVisible(False)
        self.delete_btn.setVisible(False)
        self.create_btn.setVisible(True)

    def _show_form(self, edit_mode: bool = False) -> None:
        self.stacked.setCurrentIndex(1)
        self.cancel_btn.setVisible(True)
        self.save_btn.setVisible(True)
        self.delete_btn.setVisible(edit_mode and self._note is not None)
        self.create_btn.setVisible(False)

    def _cancel_edit(self) -> None:
        self._load_note()  # Reload to reset form

    def _save(self) -> None:
        teaching = self.teaching_combo.currentText()
        atmosphere = self.atmosphere_combo.currentText()
        lesson_content = self.lesson_content_edit.toPlainText().strip() or None
        homework = self.homework_edit.toPlainText().strip() or None

        try:
            if self._is_edit_mode and self._note:
                self._service.update_note(
                    session_id=self._session_id,
                    teaching_progress=teaching,
                    class_atmosphere=atmosphere,
                    lesson_content=lesson_content,
                    homework=homework,
                )
                QMessageBox.information(self, "Success", "Teaching Note updated.")
            else:
                self._service.create_note(
                    session_id=self._session_id,
                    teaching_progress=teaching,
                    class_atmosphere=atmosphere,
                    lesson_content=lesson_content,
                    homework=homework,
                )
                QMessageBox.information(self, "Success", "Teaching Note created.")
                self._is_edit_mode = True

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
                self._show_empty()
                QMessageBox.information(self, "Deleted", "Teaching note deleted.")
                self.note_deleted.emit()
            except Exception as e:
                logger.exception("Error deleting note")
                QMessageBox.critical(self, "Error", "Could not delete teaching note.")

    def set_session(self, session_id: int) -> None:
        """Allow external refresh."""
        self._session_id = session_id
        self._load_note()