# -*- coding: utf-8 -*-
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QComboBox, QPlainTextEdit,
    QDialog, QFormLayout, QDialogButtonBox
)

from centermanager.models.note import Note, NoteType
from centermanager.services.student_note_service import StudentNoteService
from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING, BORDER_RADIUS


class NoteDetailDialog(QDialog):
    def __init__(self, note_service: StudentNoteService, note_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = note_service
        self._note_id = note_id
        self._note: Optional[Note] = None
        self.setWindowTitle("Note Details")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.type_label = QLabel()
        self.content_label = QLabel()
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Type:", self.type_label)
        form.addRow("Content:", self.content_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_note()

    def _load_note(self) -> None:
        try:
            self._note = self._service.get_note_by_id(self._note_id)
            if self._note:
                self.type_label.setText(self._note.note_type)
                self.content_label.setText(self._note.content)
            else:
                self.type_label.setText("Not found")
                self.content_label.setText("")
        except Exception as e:
            self.type_label.setText("Error")
            self.content_label.setText(str(e))


class NoteEditDialog(QDialog):
    def __init__(self, note_service: StudentNoteService, note_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = note_service
        self._note_id = note_id
        self._note: Optional[Note] = None
        self.setWindowTitle("Edit Note")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.type_combo = QComboBox()
        for t in NoteType.choices():
            self.type_combo.addItem(t)
        form.addRow("Type", self.type_combo)

        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("Enter note content...")
        self.content_edit.setMinimumHeight(100)
        form.addRow("Content", self.content_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_note()

    def _load_note(self) -> None:
        try:
            self._note = self._service.get_note_by_id(self._note_id)
            if self._note:
                idx = self.type_combo.findText(self._note.note_type)
                if idx >= 0:
                    self.type_combo.setCurrentIndex(idx)
                self.content_edit.setPlainText(self._note.content)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.reject()

    def _save(self) -> None:
        note_type = self.type_combo.currentText()
        content = self.content_edit.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Validation", "Content cannot be empty.")
            return
        try:
            self._service.update_note(self._note_id, note_type, content)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class NoteCard(QFrame):
    def __init__(self, note: Note, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._note = note
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
                padding: 6px 10px;
                margin: 2px 0;
            }
            QFrame:hover {
                background: #f5f5f5;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        type_label = QLabel(note.note_type)
        type_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1976d2;")
        header.addWidget(type_label)
        time_label = QLabel(note.created_at.strftime("%d/%m/%Y %H:%M"))
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addStretch()
        header.addWidget(time_label)

        self.edit_btn = QPushButton("✎")
        self.edit_btn.setStyleSheet("background: transparent; border: none; font-size: 14px;")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.clicked.connect(self._edit)
        header.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("✕")
        self.delete_btn.setStyleSheet("background: transparent; border: none; color: red; font-size: 14px;")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._delete)
        header.addWidget(self.delete_btn)

        layout.addLayout(header)

        content_label = QLabel(note.content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 13px; color: #333;")
        layout.addWidget(content_label)

    def _edit(self) -> None:
        parent = self.parent()
        while parent and not isinstance(parent, NotesWidget):
            parent = parent.parent()
        if parent and hasattr(parent, '_edit_note'):
            parent._edit_note(self._note.id)

    def _delete(self) -> None:
        parent = self.parent()
        while parent and not isinstance(parent, NotesWidget):
            parent = parent.parent()
        if parent and hasattr(parent, '_delete_note'):
            parent._delete_note(self._note.id)

    def mouseDoubleClickEvent(self, event) -> None:
        parent = self.parent()
        while parent and not isinstance(parent, NotesWidget):
            parent = parent.parent()
        if parent and hasattr(parent, '_on_view_note'):
            parent._on_view_note(self._note.id)


class NotesWidget(QWidget):
    note_changed = Signal()

    def __init__(self, note_service: StudentNoteService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = note_service
        self._student_id: Optional[int] = None
        self._notes: List[Note] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        header = QHBoxLayout()
        header.addStretch()
        self.add_btn = QPushButton("+ Add Note")
        self.add_btn.setFixedHeight(32)
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, SPACING['xs'], 0, 0)
        self.container_layout.setSpacing(SPACING['xs'])
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self._load_notes()

    def _load_notes(self) -> None:
        if self._student_id is None:
            return
        try:
            self._notes = self._service.get_notes_for_student(self._student_id)
        except Exception:
            self._notes = []
        self._update_ui()

    def _update_ui(self) -> None:
        self._clear_container()
        if not self._notes:
            empty = QLabel("No notes yet.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #999; padding: 20px;")
            self.container_layout.addWidget(empty)
            self.container_layout.addStretch()
            return

        for note in self._notes:
            card = NoteCard(note)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_add(self) -> None:
        if self._student_id is None:
            return
        dialog = NoteDialog(self._service, self._student_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_notes()
            self.note_changed.emit()

    def _on_view_note(self, note_id: int) -> None:
        dialog = NoteDetailDialog(self._service, note_id, parent=self)
        dialog.exec()

    def _edit_note(self, note_id: int) -> None:
        dialog = NoteEditDialog(self._service, note_id, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._load_notes()
            self.note_changed.emit()

    def _delete_note(self, note_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this note?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_note(note_id)
                self._load_notes()
                self.note_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled)


class NoteDialog(QDialog):
    def __init__(self, note_service: StudentNoteService, student_id: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = note_service
        self._student_id = student_id
        self.setWindowTitle("Add Note")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.type_combo = QComboBox()
        for t in NoteType.choices():
            self.type_combo.addItem(t)
        form.addRow("Type", self.type_combo)

        self.content_edit = QPlainTextEdit()
        self.content_edit.setPlaceholderText("Enter note content...")
        self.content_edit.setMinimumHeight(100)
        form.addRow("Content", self.content_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        note_type = self.type_combo.currentText()
        content = self.content_edit.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Validation", "Content cannot be empty.")
            return
        try:
            self._service.create_note(self._student_id, note_type, content)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))