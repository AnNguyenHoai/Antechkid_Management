# -*- coding: utf-8 -*-
"""
NotesWidget - display and manage student notes.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox, QComboBox, QPlainTextEdit,
    QDialog, QFormLayout, QDialogButtonBox
)

from centermanager.models.note import Note, NoteType
from centermanager.services.student_note_service import StudentNoteService


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
        """)
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
        layout.addLayout(header)

        content_label = QLabel(note.content)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 13px; color: #333;")
        layout.addWidget(content_label)


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
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("📝 Notes")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.add_btn = QPushButton("+ Add Note")
        self.add_btn.clicked.connect(self._on_add)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 4, 0, 0)
        self.container_layout.setSpacing(4)
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