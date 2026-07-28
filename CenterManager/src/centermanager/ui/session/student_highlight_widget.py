# -*- coding: utf-8 -*-
"""
StudentHighlightWidget - UI for adding, editing, and deleting highlights.
Now with improved empty state and auto-refresh.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFormLayout, QComboBox, QLineEdit, QPlainTextEdit,
    QScrollArea, QFrame, QMessageBox, QStackedWidget
)

from centermanager.models.student_highlight import HighlightType, StudentHighlight
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService

logger = logging.getLogger(__name__)


class StudentHighlightWidget(QWidget):
    highlight_changed = Signal()

    def __init__(
        self,
        highlight_service: StudentHighlightService,
        session_id: int,
        student_service: StudentService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = highlight_service
        self._session_id = session_id
        self._student_service = student_service
        self._highlights: List[StudentHighlight] = []
        self._editing_id: Optional[int] = None
        self._setup_ui()
        self._load_highlights()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Add form (collapsible?)
        self.form_frame = QFrame()
        self.form_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.form_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #fafafa;
                padding: 8px 12px;
            }
        """)
        form_layout = QVBoxLayout(self.form_frame)

        title_label = QLabel("Add Highlight")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        form_layout.addWidget(title_label)

        form = QFormLayout()
        form.setSpacing(6)

        # Student (combobox)
        self.student_combo = QComboBox()
        self._load_students()
        form.addRow("Student *", self.student_combo)

        # Type (combobox)
        self.type_combo = QComboBox()
        for t in HighlightType.choices():
            self.type_combo.addItem(HighlightType.display_name(t), t)
        form.addRow("Type *", self.type_combo)

        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Highlight title")
        form.addRow("Title *", self.title_edit)

        # Description
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setPlaceholderText("Optional description")
        self.desc_edit.setMaximumHeight(80)
        form.addRow("Description", self.desc_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_edit)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.save_btn)
        form.addRow(btn_layout)

        form_layout.addLayout(form)
        layout.addWidget(self.form_frame)

        self.save_btn.clicked.connect(self._save)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Existing highlights list
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(6)
        self.container_layout.setContentsMargins(0, 4, 0, 0)
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

    def _load_students(self) -> None:
        """Load students for the class."""
        try:
            students = self._student_service.list_students()
            self.student_combo.clear()
            for s in students:
                self.student_combo.addItem(f"{s.full_name} ({s.student_code})", s.id)
        except Exception as e:
            logger.exception("Error loading students")

    def _load_highlights(self) -> None:
        try:
            self._highlights = self._service.get_highlights_for_session(self._session_id)
        except Exception as e:
            logger.exception("Error loading highlights")
            self._highlights = []
        self._update_list()

    def _update_list(self) -> None:
        self._clear_container()
        if not self._highlights:
            # Empty state
            empty_widget = QWidget()
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(4)
            icon = QLabel("⭐")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("font-size: 28px;")
            empty_layout.addWidget(icon)

            title = QLabel("No Student Highlights Today")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 16px; font-weight: bold;")
            empty_layout.addWidget(title)

            desc = QLabel("Record important student observations.")
            desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc.setStyleSheet("color: #666; font-size: 14px;")
            empty_layout.addWidget(desc)

            self.container_layout.addWidget(empty_widget)
            self.container_layout.addStretch()
            return

        for h in self._highlights:
            card = self._create_highlight_card(h)
            self.container_layout.addWidget(card)
        self.container_layout.addStretch()

    def _create_highlight_card(self, highlight: StudentHighlight) -> QFrame:
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        card.setStyleSheet("""
            QFrame {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background: white;
                padding: 6px 10px;
                margin: 2px 0;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        # Header: student name, type, buttons
        header = QHBoxLayout()
        student_name = highlight.student.full_name if highlight.student else "Student"
        name_label = QLabel(student_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(name_label)

        type_display = HighlightType.display_name(highlight.type)
        type_label = QLabel(type_display)
        type_label.setStyleSheet("color: #555; font-size: 12px;")
        header.addWidget(type_label)

        header.addStretch()

        # Time
        time_str = highlight.created_at.strftime("%H:%M") if highlight.created_at else ""
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #888; font-size: 11px;")
        header.addWidget(time_label)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedWidth(50)
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedWidth(60)
        delete_btn.setStyleSheet("color: #d32f2f;")
        header.addWidget(edit_btn)
        header.addWidget(delete_btn)
        layout.addLayout(header)

        # Title and description
        title_label = QLabel(highlight.title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        layout.addWidget(title_label)
        if highlight.description:
            desc_label = QLabel(highlight.description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #555; font-size: 13px;")
            layout.addWidget(desc_label)

        edit_btn.clicked.connect(lambda: self._start_edit(highlight.id))
        delete_btn.clicked.connect(lambda: self._delete_highlight(highlight.id))

        return card

    def _clear_container(self) -> None:
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _start_edit(self, highlight_id: int) -> None:
        highlight = next((h for h in self._highlights if h.id == highlight_id), None)
        if not highlight:
            return
        self._editing_id = highlight_id
        # Populate form
        idx = self.student_combo.findData(highlight.student_id)
        if idx >= 0:
            self.student_combo.setCurrentIndex(idx)
        idx_type = self.type_combo.findData(highlight.type)
        if idx_type >= 0:
            self.type_combo.setCurrentIndex(idx_type)
        self.title_edit.setText(highlight.title)
        self.desc_edit.setPlainText(highlight.description or "")
        self.save_btn.setText("Update")
        self.cancel_btn.setVisible(True)

    def _cancel_edit(self) -> None:
        self._editing_id = None
        self._clear_form()
        self.save_btn.setText("Save")
        self.cancel_btn.setVisible(False)

    def _clear_form(self) -> None:
        self.student_combo.setCurrentIndex(0)
        self.type_combo.setCurrentIndex(0)
        self.title_edit.clear()
        self.desc_edit.clear()

    def _save(self) -> None:
        student_id = self.student_combo.currentData()
        highlight_type = self.type_combo.currentData()
        title = self.title_edit.text().strip()
        description = self.desc_edit.toPlainText().strip()

        if not student_id:
            QMessageBox.warning(self, "Validation Error", "Please select a student.")
            return
        if not highlight_type:
            QMessageBox.warning(self, "Validation Error", "Please select a type.")
            return
        if not title:
            QMessageBox.warning(self, "Validation Error", "Title is required.")
            return

        try:
            if self._editing_id:
                self._service.update_highlight(
                    highlight_id=self._editing_id,
                    highlight_type=highlight_type,
                    title=title,
                    description=description,
                )
                QMessageBox.information(self, "Success", "Highlight updated.")
                self._cancel_edit()
            else:
                self._service.create_highlight(
                    session_id=self._session_id,
                    student_id=student_id,
                    highlight_type=highlight_type,
                    title=title,
                    description=description,
                )
                QMessageBox.information(self, "Success", "Highlight added.")
                self._clear_form()
            self._load_highlights()
            self.highlight_changed.emit()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))
        except Exception as e:
            logger.exception("Error saving highlight")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")

    def _delete_highlight(self, highlight_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this highlight? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.delete_highlight(highlight_id)
                self._load_highlights()
                self.highlight_changed.emit()
            except Exception as e:
                logger.exception("Error deleting highlight")
                QMessageBox.critical(self, "Error", "Could not delete highlight.")