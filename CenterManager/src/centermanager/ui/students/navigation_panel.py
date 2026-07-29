# -*- coding: utf-8 -*-
"""
NavigationPanel - redesigned student list with avatar, name, code, status, class, last updated.
"""
import logging
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QFrame, QPushButton, QSizePolicy, QScrollArea
)

from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.ui.common.avatar import Avatar
from centermanager.ui.common.search_bar import SearchBar
from centermanager.ui.common.empty_state import EmptyState
from centermanager.ui import styles

logger = logging.getLogger(__name__)


class StudentListItem(QFrame):
    """Custom item for student list with avatar and details."""

    def __init__(self, student: Student, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._student = student
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(styles.LIST_ITEM)
        self.setFixedHeight(60)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Avatar
        avatar = Avatar(self._student.full_name, size=36)
        layout.addWidget(avatar)

        # Name and code
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)

        name_label = QLabel(self._student.full_name)
        name_label.setStyleSheet("font-size: 14px; font-weight: 500;")
        info_layout.addWidget(name_label)

        code_label = QLabel(self._student.student_code)
        code_label.setStyleSheet("font-size: 12px; color: #888;")
        info_layout.addWidget(code_label)

        layout.addLayout(info_layout)

        # Status badge
        status = self._student.status or "ACTIVE"
        status_color = "#4caf50" if status == "ACTIVE" else "#ff9800"
        status_label = QLabel(status)
        status_label.setStyleSheet(f"""
            background: {status_color}22;
            color: {status_color};
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            font-weight: 500;
        """)
        layout.addWidget(status_label)

        layout.addStretch()

        # Last updated
        if self._student.updated_at:
            time_str = self._student.updated_at.strftime("%d/%m/%Y")
            time_label = QLabel(time_str)
            time_label.setStyleSheet("font-size: 11px; color: #aaa;")
            layout.addWidget(time_label)

    @property
    def student(self) -> Student:
        return self._student


class NavigationPanel(QWidget):
    """Redesigned student list with search and filter."""

    student_selected = Signal(int)
    filter_clicked = Signal()

    def __init__(
        self,
        student_service: Optional[StudentService] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background: white;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar: Search + Filter
        toolbar = QWidget()
        toolbar.setStyleSheet("background: white; padding: 8px 12px; border-bottom: 1px solid #e8e8e8;")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)

        # Search bar
        self.search_bar = SearchBar()
        self.search_bar.text_changed.connect(self._filter)
        toolbar_layout.addWidget(self.search_bar)

        # Filter row
        filter_row = QHBoxLayout()
        self.filter_btn = QPushButton("🔍 Filter")
        self.filter_btn.setStyleSheet(styles.BUTTON_SECONDARY)
        self.filter_btn.setFixedHeight(28)
        self.filter_btn.clicked.connect(self.filter_clicked.emit)
        filter_row.addWidget(self.filter_btn)
        filter_row.addStretch()

        # Student count
        self.count_label = QLabel("0 students")
        self.count_label.setStyleSheet("font-size: 12px; color: #999;")
        filter_row.addWidget(self.count_label)

        toolbar_layout.addLayout(filter_row)
        layout.addWidget(toolbar)

        # Student list
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
                background: white;
            }
            QListWidget::item {
                padding: 0px;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
            }
        """)
        self.list_widget.setSpacing(1)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # Empty state (hidden initially)
        self.empty_widget = EmptyState(
            icon="👤",
            title="No students found",
            description="Try adjusting your search or filter."
        )
        self.empty_widget.setVisible(False)
        layout.addWidget(self.empty_widget)

    def _connect_signals(self) -> None:
        self.list_widget.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        widget = self.list_widget.itemWidget(item)
        if widget and hasattr(widget, 'student'):
            self.student_selected.emit(widget.student.id)

    def set_students(self, students: List[Student]) -> None:
        self._students = students
        self._filter(self.search_bar.text())

    def _filter(self, text: str) -> None:
        if not text.strip():
            self._filtered = self._students[:]
        else:
            if self._student_service and len(text.strip()) > 2:
                try:
                    self._filtered = self._student_service.search_students(text.strip())
                except Exception as e:
                    logger.exception("Search failed")
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
        self.count_label.setText(f"{len(self._filtered)} students")

        if not self._filtered:
            self.list_widget.setVisible(False)
            self.empty_widget.setVisible(True)
            return

        self.list_widget.setVisible(True)
        self.empty_widget.setVisible(False)

        for student in self._filtered:
            item = QListWidgetItem()
            widget = StudentListItem(student)
            item.setSizeHint(widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        self.list_widget.clearSelection()

    def select_student(self, student_id: int) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget and widget.student.id == student_id:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                break

    def refresh(self) -> None:
        self._filter(self.search_bar.text())