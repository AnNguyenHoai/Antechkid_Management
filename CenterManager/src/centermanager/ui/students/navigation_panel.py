# -*- coding: utf-8 -*-
"""
Navigation panel: Search + Student List (Code + Name only).
Uses QListWidget with custom items.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QFrame
)

from centermanager.models.student import Student

logger = logging.getLogger(__name__)


class StudentListItem(QFrame):
    """Custom widget for a student item in the list."""
    def __init__(self, student: Student, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._student = student
        self.setFrameStyle(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        self.name_label = QLabel(student.full_name)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        self.code_label = QLabel(student.student_code)
        self.code_label.setStyleSheet("font-size: 12px; color: #666;")

        layout.addWidget(self.name_label)
        layout.addWidget(self.code_label)

        self.setStyleSheet("""
            QFrame {
                border: none;
                background: transparent;
            }
            QFrame:hover {
                background: #e8e8e8;
            }
        """)

    @property
    def student(self) -> Student:
        return self._student


class NavigationPanel(QWidget):
    student_selected = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Code or Name...")
        self.search_input.setStyleSheet("padding: 6px 8px;")
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
                background: white;
            }
            QListWidget::item:selected {
                background: #d0d0ff;
                color: black;
            }
            QListWidget::item:hover:!selected {
                background: #f0f0f0;
            }
            QListWidget::item {
                padding: 0px;
            }
        """)
        self.list_widget.setSpacing(1)
        layout.addWidget(self.list_widget)

        # Empty label for no results
        self.empty_label = QLabel("No students found.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #999; font-size: 14px; padding: 20px 0;")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

    def _connect_signals(self) -> None:
        self.search_input.textChanged.connect(self._filter)
        self.list_widget.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.list_widget.itemWidget(item)
        if widget and hasattr(widget, 'student'):
            self.student_selected.emit(widget.student.id)

    def set_students(self, students: List[Student]) -> None:
        self._students = students
        self._filter(self.search_input.text())

    def _filter(self, text: str) -> None:
        if not text.strip():
            self._filtered = self._students[:]
        else:
            lower = text.strip().lower()
            self._filtered = [
                s for s in self._students
                if lower in s.student_code.lower() or lower in s.full_name.lower()
            ]
        self._populate_list()

    def _populate_list(self) -> None:
        self.list_widget.clear()
        if not self._filtered:
            self.empty_label.setVisible(True)
            self.list_widget.setVisible(False)
            return

        self.empty_label.setVisible(False)
        self.list_widget.setVisible(True)

        for student in self._filtered:
            item = QListWidgetItem()
            widget = StudentListItem(student)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        # Clear selection
        self.list_widget.clearSelection()

    def select_student(self, student_id: int) -> None:
        """Programmatically select a student by ID."""
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and widget.student.id == student_id:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                break

    def refresh(self) -> None:
        self._filter(self.search_input.text())